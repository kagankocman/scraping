from django.shortcuts import render, redirect
from django.http import HttpResponse
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from django.http import FileResponse
from textblob import TextBlob
from datetime import datetime



# MongoDB bağlantısı
connection_string = "mongodb+srv://aslidurucn:Asli.duruc4n58@cluster0.dikncvv.mongodb.net/mydatabse"
client = MongoClient(connection_string)
db = client["mydatabase"]
collection = db["mycollection"]



def get_datas_from_link(link):
    sayfa = requests.get(link)
    html_sayfa = BeautifulSoup(sayfa.content, "html.parser")

    data_dict = {}  

    # Yayın ID
    header_div = html_sayfa.find("div", class_="header-breadcrumbs-mobile")
    if header_div:
        strong_tag = header_div.find("strong")
        if strong_tag:
            yayin_id_text = strong_tag.text.strip()
            # "arXiv" kısmını çıkar
            data_dict["YayinID"] = yayin_id_text.split(":")[1].strip() if ":" in yayin_id_text else yayin_id_text.strip()


    # Yayın Adı
    title_h1 = html_sayfa.find("h1", class_="title mathjax")
    if title_h1:
        title_text = title_h1.text.strip()
        descriptor_index = title_text.find("Title:")
        if descriptor_index != -1:
            data_dict["YayinAdi"] = title_text[descriptor_index + len("Title:"):].strip()

    # Yazarlar
    authors_div = html_sayfa.find("div", class_="authors")
    if authors_div:
        a_tags = authors_div.find_all("a")
        authors = [a.text.strip() for a in a_tags]
        data_dict["Yazarlar"] = authors


    # Tür
    type_spans = html_sayfa.find_all("span", class_="primary-subject")
    yayin_turleri = [type_span.text.strip() for type_span in type_spans]
    data_dict["YayinTuru"] = yayin_turleri

    # Yayımcı adı
    submission_history_div = html_sayfa.find("div", class_="submission-history")
    if submission_history_div:
        submission_text = submission_history_div.text.strip()
        email_link = submission_history_div.find("a", href=lambda href: href and "show-email" in href)
        if email_link:
            publisher_name = submission_text.split("From: ")[1].split("[")[0].strip()
            data_dict["YayinciAdi"] = publisher_name

    # Özet
    abstract_block = html_sayfa.find("blockquote", class_="abstract mathjax")
    if abstract_block:
        abstract_text = abstract_block.text.strip()
        abstract_descriptor_index = abstract_text.find("Abstract:")
        if abstract_descriptor_index != -1:
            data_dict["Ozet"] = abstract_text[abstract_descriptor_index + len("Abstract:"):].strip()

    # Referanslar
    references_div = html_sayfa.find("div", class_="extra-ref-cite")
    if references_div:
        reference_links = references_div.find_all("a")
        references = [reference_link['href'] for reference_link in reference_links]
        data_dict["Referanslar"] = references

    # URL
    data_dict["URL"] = link

    # Yayımlanma Tarihi
    dateline_div = html_sayfa.find("div", class_="submission-history")
    if dateline_div:
        strong_tag = dateline_div.find('strong')
        submission_date = strong_tag.next_sibling.strip()
        submission_date = submission_date.split('(')[0].strip()
        data_dict["YayinlanmaTarihi"] = submission_date
        
    # DOI numarası
    doi_link = html_sayfa.find("a", {"data-doi": True})
    if doi_link:
        data_dict["Doi"] = doi_link["data-doi"]
    else:
        data_dict["Doi"] = None

    # Anahtar Kelimeler
    subjects_td = html_sayfa.find('td', class_='tablecell subjects')
    if subjects_td:
        subjects = subjects_td.text.split(';')
        anahtar_kelimeler = [subject.strip() for subject in subjects if subject.strip()]
        data_dict["MakaleAnahtarKelimeleri"] = anahtar_kelimeler

    return data_dict




def home(request):
    if request.method == 'POST':
        kelime = request.POST.get('search_keyword')  
        print("Arama Kelimesi:", kelime)  
        corrected_kelime = correct_spelling(kelime)  
        print("Düzeltme Sonrası Arama Kelimesi:", corrected_kelime)  
        url = f"https://arxiv.org/search/?query={corrected_kelime}&searchtype=all&source=header"
        sayfa = requests.get(url)
        if sayfa.status_code == 200:
            html_sayfa = BeautifulSoup(sayfa.content, "html.parser")
            baglantilar = html_sayfa.find_all("p", class_="list-title is-inline-block")
            if baglantilar:
                for baglanti in baglantilar[:10]:
                    link = baglanti.find("a")
                    if link:
                        data_dict = get_datas_from_link(link['href'])  # Linkten verileri al
                        data_dict["Kelime"] = corrected_kelime  # Düzeltme sonrası arama kelimesini veri sözlüğüne ekle
                        collection.insert_one(data_dict)  # Veriyi MongoDB'ye kaydet
                return redirect('search_results')  # Arama sonuçlarına yönlendir
            else:
                print("Hata: Bağlantılar bulunamadı.") 
                return HttpResponse("Bağlantılar bulunamadı.")
        else:
            print("Hata: Arxiv'den veri çekilirken bir hata oluştu.")  
            return HttpResponse("Arxiv'den veri çekilirken bir hata oluştu.")
    else:
        return render(request, 'home.html')

    

def search_results(request):
    kelime = request.GET.get('Kelime')  # GET isteğiyle gelen kelimeyi al
    filters = request.GET.getlist('filters') if request.GET.get('filters') else []  # Seçilen filtreleri al
    query = {}  # MongoDB sorgusu için boş bir sözlük oluştur

    if kelime:
        # Arama kelimesine göre filtreleme ekle
        query["$text"] = {"$search": kelime}

    # Seçilen filtreleri MongoDB sorgusuna ekle
    for filter in filters:
        query[filter] = {"$exists": True}

    # Sıralama türünü al
    sort_type = request.GET.get('sort')
    if sort_type == 'yeniden_eskiye':
        sort_order = -1 
    elif sort_type == 'eskiden_yeniye':
        sort_order = 1  
    else:
        sort_order = -1  
    # MongoDB sorgusu
    results = collection.find(query).sort([('YayinlanmaTarihi', sort_order)]).limit(10)

    # Filtrelerin listesini ve sıralama türünü view ile paylaş
    return render(request, 'search_results.html', {'results': results, 'selected_filters': filters})



def view_details(request, yayin_id):
    # MongoDB'den yayın detaylarını getir
    result = collection.find_one({"YayinID": yayin_id})
    
    return render(request, 'view_details.html', {'result': result})



def download_pdf(request, yayin_id):
    # MongoDB'den yayın detaylarını getir
    result = collection.find_one({"YayinID": yayin_id})

    # İlgili PDF dosyasının URL'sini oluştur
    pdf_url = f"https://arxiv.org/pdf/{yayin_id}"

    # PDF dosyasını indir
    response = requests.get(pdf_url)
       
    if response.status_code == 200:
        # Dosyayı kullanıcıya geri döndür
        return HttpResponse(response.content, content_type='application/pdf')
    else:
        return HttpResponse("PDF dosyası indirilemedi.")

def correct_spelling(keyword):
    # Yazım yanlışı düzeltme işlemini gerçekleştir
    corrected_keyword = str(TextBlob(keyword).correct())
    return corrected_keyword


