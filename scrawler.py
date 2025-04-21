import requests
import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import subprocess
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor


def get_one_page_urls(r):
    one_page_video_urls = []
    soup = BeautifulSoup(r.text, 'html.parser')
    elements = soup.select(".has-text-grey-dark")
    video_duration = soup.select(".duration")
    for e in elements[0::2]:
        one_page_video_urls.append(e["href"])
    return one_page_video_urls

def get_video_ids(r):
    ids = []
    soup = BeautifulSoup(r.text, 'html.parser')
    t = soup.find_all(name='img',attrs={'loading':'lazy'})[0].get('src')
    for i in soup.find_all(name='img', attrs={'loading': 'lazy'}):
        ids.append(re.search(r'/(\d+)\.webp$', i.get('src')).group()[1:-5])
    return ids

def get_cnds(r):
    soup = BeautifulSoup(r.text, 'html.parser')
    pass

def get_video_info(r):
    soup = BeautifulSoup(r.text, 'html.parser')
    m3u8_pattern = r'm3u8\?t=([^&]+)&m=([A-Za-z0-9_\-]+)'
    favorites_pattern = r'"favorites":\d+,'
    m3u8 = re.search(m3u8_pattern, r.text).group()
    favorites = re.search(favorites_pattern, r.text).group()
    title = soup.find(name='meta', attrs={'property': 'twitter:title'}).get('content')
    uploader = soup.find(name='meta', attrs={'property': 'twitter:creator'}).get('content')
    date_pattern = "(([0-9]{3}[1-9]|[0-9]{2}[1-9][0-9]{1}|[0-9]{1}[1-9][0-9]{2}|[1-9][0-9]{3})-(((0[13578]|1[02])-(0[1-9]|[12][0-9]|3[01]))|" + "((0[469]|11)-(0[1-9]|[12][0-9]|30))|(02-(0[1-9]|[1][0-9]|2[0-8]))))|((([0-9]{2})(0[48]|[2468][048]|[13579][26])|" + "((0[48]|[2468][048]|[3579][26])00))-02-29)$"
    upload_date = re.search(date_pattern, soup.select(".content.is-size-7")[0].text).group()
    return m3u8, title, favorites, uploader, upload_date

def get_ts_urls(r):
    with open("index.m3u8", "wb") as f:
        f.write(r.content)
    with open("index.m3u8", "r") as f:
        lines = f.readlines()
    ts_urls = [line.strip() for line in lines if line.endswith(".ts\n")]
    return ts_urls

def download_ts(url, index):
    save_path = f"ts_files/{index:04d}.ts"  # 按 0001.ts, 0002.ts 格式保存
    response = requests.get(url, stream=True)
    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    print(f"已下载：{save_path}")

def merge_ts(output_file):
    with open(output_file, "wb") as merged:
        for ts_file in sorted(os.listdir("ts_files")):
            with open(f"ts_files/{ts_file}", "rb") as f:
                merged.write(f.read())

def clear_folder(folder_path):
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

def del_trash(r,one_page_video_urls,ids):
    del_urls = []
    del_ids = []
    soup = BeautifulSoup(r.text, 'html.parser')
    video_duration = soup.select(".duration")
    for i in range(len(video_duration)):
        if int(video_duration[i].text[3:5]) >= 20:
            del_urls.append(one_page_video_urls[i])
            del_ids.append(ids[i])
    pure_urls = list(filter(lambda x: x not in del_urls, one_page_video_urls))
    pure_ids = list(filter(lambda x: x not in del_ids, ids))
    return pure_urls, pure_ids

def main():
    base_url = 'https://zvm.xinhua107.com/'
    favorite_url = base_url+'video/category/most-favorite/'
    cdns = ["cdn2.jiuse3.cloud","fdc100g2b.jiuse.cloud","dp.jiuse.cloud","shark10g2.jiuse.cloud"]
    pages = range(19,20)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    # 创建存储目录
    if not os.path.exists('video'):
        os.makedirs('video')
    if not os.path.exists('ts_files'):
        os.makedirs("ts_files")
    for page in pages:
        r_page = requests.get(favorite_url + str(page), headers=headers)

        #获取当前页面所有视频的链接，用来进入每个视频的页面
        #返回的url没有base，这里处理一下
        t_one_page_video_urls = get_one_page_urls(r_page)
        t2_one_page_video_urls = [base_url+t for t in t_one_page_video_urls]
        #获取当前页面所有视频的id，用来下载m3u8和ts文件，需要拼接这两个的链接
        t_ids = get_video_ids(r_page)
        one_page_video_urls, ids = del_trash(r_page,t2_one_page_video_urls,t_ids)

        #接下来进入每个视频的页面进行下载。这里需要遍历视频主页和视频id所以用for循环
        for i in range(7,len(one_page_video_urls)):#len(one_page_video_urls)
            print(f'processing page {page} video {i}')
            r_video = requests.get(one_page_video_urls[i], headers=headers)

            #获取视频的信息
            m3u8, title, favorites, uploader, upload_date = get_video_info(r_video)
            print(title)
            m3u8_url = 'https://'+cdns[0]+'/hls/' + ids[i] + '/index.'+m3u8
            r_m3u8 = requests.get(m3u8_url, headers=headers)

            # 获取ts文件链接
            ts_urls = get_ts_urls(r_m3u8)
            full_ts_urls = ['https://cdn2.jiuse3.cloud/hls/' + ids[i] + '/' + url for url in ts_urls]
            clear_folder('ts_files')
            # 下载ts文件
            with ThreadPoolExecutor(max_workers=8) as executor:  # 控制并发线程数
                for idx, url in enumerate(full_ts_urls, start=1):
                    executor.submit(download_ts, url, idx)
            # 合并ts文件
            title,favorites,uploader,upload_date = [x.replace('/','') for x in [title,favorites,uploader,upload_date]]
            file_name = f'./video/p10-19/{str(page)}-{str(i)}-{title}-{favorites}-{uploader}-{upload_date}.mp4'
            merge_ts(file_name)

if __name__ == '__main__':
    main()