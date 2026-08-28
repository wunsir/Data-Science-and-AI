import time
import csv
import os
import pandas as pd
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


def get_target_info_selenium(driver, results):
    """使用selenium解析网页元素，获取目标数据"""
    try:
        # 等待职位列表加载完成
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "positionlist"))
        )
        # 获取所有职位项
        job_items = driver.find_elements(By.CSS_SELECTOR, ".joblist-box__item")
        for job_item in job_items:
            try:
                # 岗位名称
                job_name_element = job_item.find_element(By.CSS_SELECTOR, ".jobinfo__name")
                job_name = job_name_element.text.strip()

                # 公司名称
                company_name_element = job_item.find_element(By.CSS_SELECTOR, ".companyinfo__name")
                company_name = company_name_element.text.strip()

                # 薪资
                salary_element = job_item.find_element(By.CSS_SELECTOR, ".jobinfo__salary")
                salary = salary_element.text.strip()

                # 工作地点和经验要求
                try:
                    job_info_elements = job_item.find_elements(By.CSS_SELECTOR, ".jobinfo__other-info-item")
                    location = ""
                    experience = ""
                    education = ""
                    if len(job_info_elements) >= 1:
                        location = job_info_elements[0].text.strip()
                    if len(job_info_elements) >= 2:
                        experience = job_info_elements[1].text.strip()
                    if len(job_info_elements) >= 3:
                        education = job_info_elements[2].text.strip()

                    # 组装岗位要求
                    job_requirement = f"{experience},{education}"
                except Exception as e:
                    print(f"获取岗位要求信息出错:{e}")
                    job_requirement = "暂无"
                    location = "暂无"

                # 技术要求(标签)
                requirement_tags = []
                try:
                    tag_elements = job_item.find_elements(
                        By.CSS_SELECTOR,
                        'div.jobinfo__tag .joblist-box__item-tag'  # 上层div（类jobinfo__tag）下的目标元素
                    )
                    for tag in tag_elements:
                        requirement_tags.append(tag.text.strip())
                except Exception as e:
                    print(f"获取职位要求出错:{e}")

                requirement = ",".join(requirement_tags) if requirement_tags else "暂无"

                # 公司(标签)
                company_tags = []
                try:
                    tag_elements = job_item.find_elements(
                        By.CSS_SELECTOR,
                        'div.companyinfo__tag .joblist-box__item-tag'  # 上层div（类jobinfo__tag）下的目标元素
                    )
                    for tag in tag_elements:
                        company_tags.append(tag.text.strip())
                except Exception as e:
                    print(f"获取公司信息出错:{e}")

                ct = ",".join(company_tags) if company_tags else "暂无"

                # 添加到结果列表
                results.append([job_name, company_name, salary, job_requirement, location, requirement, ct])
            except Exception as e:
                print(f"解析单个职位信息出错:{e}")
                continue
    except Exception as e:
        print(f"获取职位列表出错:{e}")


def write2file(current_page, results, fileType, savePath):
    """将解析的数据写入指定文件类型"""
    # 创建保存目录
    save_dir = os.path.join(savePath, "zhaopin_data")
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    if fileType.endswith(".xlsx") or fileType.endswith(".xls"):
        file_path = os.path.join(save_dir, 'zhilianzhaopin_python.xlsx')

        # 将结果转换为DataFrame
        df = pd.DataFrame(results[1:], columns=results[0])  # 第一行作为列名

        # 如果是第一页，直接写入；否则追加写入
        if current_page == 1:
            df.to_excel(file_path, index=False, engine='openpyxl')
        else:
            # 读取现有数据并追加新数据
            existing_df = pd.read_excel(file_path, engine='openpyxl')
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.to_excel(file_path, index=False, engine='openpyxl')

        print(f'第{current_page}页爬取数据保存Excel成功!')

    elif fileType.endswith(".csv"):
        # 保留原有的CSV保存功能
        save_dir_csv = os.path.join(savePath, 'to_csv')
        if not os.path.exists(save_dir_csv):
            os.makedirs(save_dir_csv)

        file_path = os.path.join(save_dir_csv, 'zhilianzhaopin_python.csv')

        # 如果是第一页，写入表头
        if current_page == 1:
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as wf:
                writer = csv.writer(wf)
                writer.writerow(['岗位名称', '公司名称', '岗位薪资', '岗位要求', '公司位置', '技术要求', '企业信息'])

        # 追加写入数据
        with open(file_path, 'a', encoding='utf-8-sig', newline='') as af:
            writer = csv.writer(af)
            # 跳过表头，只写入数据行
            for row in results[1:]:  # 跳过表头
                writer.writerow(row)

        print(f'第{current_page}页爬取数据保存csv成功!')



def process_zhilianzhaopin_selenium(baseUrl, pages, fileType, savePath):
    """使用selenium处理智联招聘爬虫"""
    # 设置Chrome选项
    chrome_options = Options()
    # chrome_options.add_argument('--headless')  # 无头模式
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    # 初始化WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    try:
        results = [['岗位名称', '公司名称', '岗位薪资', '岗位要求', '公司位置', '技术要求', '企业信息']]

        # 根据入参pages,拼接请求url,控制爬取的页数
        for page in range(1, int(pages) + 1):
            url = baseUrl + str(page)
            print(f"正在爬取第{page}页:{url}")

            # 访问页面
            driver.get(url)

            # 等待页面加载
            time.sleep(3)

            # 解析网页源代码中的目标数据
            get_target_info_selenium(driver, results)

            # 写入文件
            write2file(page, results, fileType, savePath)

            # 清空results，为下一页准备(保留表头)
            results = [['岗位名称', '公司名称', '岗位薪资', '岗位要求', '公司位置', '技术要求', '企业信息']]

            # 随机延时，避免请求过于频繁
            delay = random.randint(3, 7)  # 生成3到7之间的随机整数
            time.sleep(delay)

        print(f'共爬取{page}页数据，解析完毕......................')

    except Exception as e:
        print(f"爬取过程中出现错误:{e}")

    finally:
        # 关闭浏览器
        driver.quit()


if __name__ == "__main__":
    # https://sou.zhaopin.com/?jl=省份&kw=关键词&p=页数
    base_url = "https://sou.zhaopin.com/?jl=765&kw=财务&p="
    save_path = "zhilian_spider"
    page_total = "30"
    process_zhilianzhaopin_selenium(base_url, page_total, ".xlsx", save_path)
