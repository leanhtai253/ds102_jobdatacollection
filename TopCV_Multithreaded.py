import pandas as pd
import numpy as np
import os
import json
import requests
from bs4 import BeautifulSoup
import time
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor 
from multiprocessing import cpu_count 
import asyncio 
import aiohttp 

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
num_cores = cpu_count() # number of CPU cores 

def save_json(file, filename):
    SAVE_DIR = "data/topcv/json"
    with open(f'{SAVE_DIR}/{filename}.json', 'w') as openfile:
        json.dump(file, openfile)

def read_json(filename):
    OPEN_DIR = "data/topcv/json"
    with open(f'{OPEN_DIR}/{filename}.json', 'r') as openfile:
        file = json.load(openfile)
    return file

def append_text(content, filename):
    OPEN_DIR = 'data/topcv/text'
    with open(f'{OPEN_DIR}/{filename}.txt', 'a') as openfile:
        openfile.write(f'{content}\n')

async def extract_details(page, session, save_name_exc_urls): 
    # concatenate page number to base URL 
    async with session.get(f"{page}") as resp:
        jobs_by_industries = []
        except_urls = []
        print(f'{page}')
        pg_bs = BeautifulSoup(await resp.text(), 'html.parser')
        job_body = pg_bs.find("div",{'class':'job-body'})
        job_list = job_body.find('div', {'class':'job-list-default'})
        job_items = job_list.find_all('div',{'class':'job-item-default'})
        for job_item in job_items:
            job_dict = {}
            job_item_ = job_item.find('div',{'class':'body'})
            job_url = job_item_.find('a').get('href')
            try:
                job_dict['url'] = job_url
                resp1 = requests.get(job_url)
                jb_bs = BeautifulSoup(resp1.text, 'html.parser')
                job_header = jb_bs.find('div',{'class':'box-detail-job'}).find('div',{'class':'box-header'})
                company_name = job_header.find('a',{'class':'company-logo'}).get('title')
                job_title = job_header.find('div',{'class':'box-info-job'}).find('h1',{'class':'job-title'}).getText().strip()
                job_deadline = job_header.find('div',{'class':'job-deadline'}).getText().strip()
                job_info = jb_bs.find('div',{'id':'tab-info'})

                general_info = job_info.find_all('div',{'class':'box-info'})[-1].find_all('div',{'class':'box-item'})
                job_salary = general_info[0].find('span').getText().strip()
                job_type = general_info[2].find('span').getText().strip()
                job_level = general_info[3].find('span').getText().strip()
                job_yoe = general_info[-1].find('span').getText().strip()
                job_addresses = [item.text.strip() for item in job_info.find('div',{'class':'box-address'}).find_all('div')[1:]]

                job_data = job_info.find('div',{'class':'job-data'})
                job_details = job_data.find_all('div',{'class':'content-tab'})
                job_desc = str(job_details[0])
                job_req = str(job_details[1])

                job_dict['job_title'] = job_title
                job_dict['job_deadline'] = job_deadline
                job_dict['company_name'] = company_name
                job_dict['job_salary'] = job_salary
                job_dict['job_type'] = job_type
                job_dict['job_yoe'] = job_yoe
                job_dict['job_addresses'] = job_addresses
                job_dict['job_desc'] = job_desc
                job_dict['job_req'] = job_req
                job_dict['job_level'] = job_level
                jobs_by_industries.append(job_dict)
#                 print(f'{len(job_title)} - {len(job_salary)} - {len(job_type)} - {len(job_addresses)} - {len(job_desc)} - {len(job_req)}')
            except Exception as e:
                except_urls.append(job_url)
        append_text(except_urls, save_name_exc_urls)
        return jobs_by_industries

async def extract_details_task(pages_for_task, save_name_exc_urls): 
    async with aiohttp.ClientSession() as session: 
        tasks = [ 
            extract_details(page, session, save_name_exc_urls) 
            for page in pages_for_task 
        ] 
        list_of_lists = await asyncio.gather(*tasks) 
        return sum(list_of_lists, []) 
 
 
def asyncio_wrapper(pages_for_task, save_name_exc_urls): 
    return asyncio.run(extract_details_task(pages_for_task, save_name_exc_urls))

def execute_parallel_scrape(pages, save_name, save_name_exc_urls): 
    executor = ProcessPoolExecutor(max_workers=num_cores) 
    tasks = [ 
        executor.submit(asyncio_wrapper, pages_for_task, save_name_exc_urls) 
        for pages_for_task in np.array_split(pages, num_cores) 
    ] 
    doneTasks, _ = concurrent.futures.wait(tasks) 
 
    results = [ 
        item.result() 
        for item in doneTasks 
    ] 
    save_json(results, save_name) 
    
def parallel_get_jobs_by_industry(industry_name, industry_url, save_name=None):
    base_url = "https://www.topcv.vn"
    ind_url = industry_url
    if save_name is None:
        save_name = industry_name
    save_name_exc_urls = f'exc_urls_{save_name}' 
    print("Collecting industry: ", industry_name)
    
    resp = requests.get(f'{base_url}{ind_url}')
    pg_bs = BeautifulSoup(resp.text, 'html.parser')
    try:
        max_page = int(pg_bs.find('ul',{'class':'pagination'}).find_all('li')[-2].text.strip())
    except Exception as e:
        max_page = 1
    print("Total page: ", max_page)
    pages_to_scrape = [f'{base_url}{ind_url}?page={i}' for i in range(1,max_page+1)]
    
    execute_parallel_scrape(pages_to_scrape, save_name, save_name_exc_urls)


if __name__ == '__main__':
    with open("data/topcv/json/industries_raw.json", 'r') as openfile:
        industries = json.load(openfile)
    for index,industry in enumerate(industries):
        industry_name = industry['name']
        industry_url = industry['access_url']
        save_name = f'top_cv_{index}'
        parallel_get_jobs_by_industry(industry_name, industry_url, save_name)