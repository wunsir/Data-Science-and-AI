# -*- coding: utf-8 -*-
# 数据爬取
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from time import sleep
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
from lxml import etree
import os
import random
import html as _html
import json


def main():
    resLs = []
    skipped = 0
    for p in range(pz):
        p += 1
        print(f'爬取第{p}页>>>')
        sleep(2)
        for i in range(140):
            sleep(random.random() / 10)
            driver.execute_script('window.scrollBy(0, 50)')
        # 等待职位列表加载（页面为 JS 渲染，需等待节点出现）
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.j_joblist > div'))
            )
        except TimeoutException:
            print('警告：等待职位列表加载超时，尝试额外滚动加载')
            for _ in range(3):
                driver.execute_script('window.scrollBy(0, 500)')
                sleep(1)
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.j_joblist > div'))
                )
            except TimeoutException:
                print('仍然找不到职位列表，继续采集当前页面（可能为空）')

        # 尝试直接使用浏览器 DOM（优先使用 sensorsdata 属性），回退到文本选择器
        items = driver.find_elements(By.CSS_SELECTOR, '.joblist-item')
        if not items:
            try:
                os.makedirs('data', exist_ok=True)
                with open(f'data/{key}_last_page.html', 'w', encoding='utf-8') as _f:
                    _f.write(driver.page_source)
                print(f'警告：未找到任何 .joblist-item，已将页面源码保存到 data/{key}_last_page.html 以便调试')
            except Exception as _e:
                print('警告：尝试保存页面源码失败：', _e)
        for it in items:
            try:
                # 尝试获取结构化属性
                job_elem = None
                try:
                    job_elem = it.find_element(By.CSS_SELECTOR, '.joblist-item-job')
                except Exception:
                    job_elem = None

                sensors = None
                if job_elem:
                    try:
                        sensors = job_elem.get_attribute('sensorsdata') or job_elem.get_attribute('sensordata')
                    except Exception:
                        sensors = None

                if sensors:
                    try:
                        info = json.loads(_html.unescape(sensors))
                        job_title = info.get('jobTitle', '')
                        job_salary = info.get('jobSalary', '')
                        job_area = info.get('jobArea', '')
                        job_year = info.get('jobYear', '')
                        job_degree = info.get('jobDegree', '')
                    except Exception as e:
                        print('警告：解析 sensorsdata 失败，回退 DOM 文本，错误：', e)
                        sensors = None

                if not sensors:
                    def safe_text(elem, selectors):
                        for sel in selectors:
                            try:
                                el = elem.find_element(By.CSS_SELECTOR, sel)
                                txt = el.text.strip()
                                if txt:
                                    return txt
                            except Exception:
                                continue
                        return ''

                    job_title = safe_text(it, ['.jname', '.jname.text-cut', '.job-title', '.jobname'])
                    job_salary = safe_text(it, ['.sal', '.sal.shrink-0', '.salary'])
                    job_area = safe_text(it, ['.area .shrink-0', '.joblist-item-bot .area .shrink-0', '.joblist-item-mid .area'])
                    extra = safe_text(it, ['.joblist-item-job .tag-list', '.joblist-item-job'])
                    job_year = ''
                    job_degree = ''
                    if extra:
                        parts = [p.strip() for p in extra.replace('/', ' ').replace('·', ' ').split() if p.strip()]
                        for p in parts:
                            if any(ch.isdigit() for ch in p) and ('年' in p or '经验' in p):
                                job_year = p
                            if p.endswith('及以上') or p in ('本科', '大专', '硕士', '博士') or '学历' in p:
                                job_degree = p

                # 公司信息
                try:
                    c_name = it.find_element(By.CSS_SELECTOR, '.cname').text.strip()
                except Exception:
                    c_name = safe_text(it, ['.cname', '.cname.text-cut'])

                # 公司字段（dc class）
                c_fields = []
                try:
                    for el in it.find_elements(By.CSS_SELECTOR, '.dc'):
                        txt = el.text.strip()
                        if txt:
                            c_fields.append(txt)
                except Exception:
                    pass

                c_field_0 = c_fields[0] if len(c_fields) > 0 else ''
                c_field_1 = c_fields[1] if len(c_fields) > 1 else ''
                c_num = c_fields[2] if len(c_fields) > 2 else '未知'

                dit = {
                    '职位': job_title,
                    '薪资': job_salary,
                    '城市': job_area,
                    '经验': job_year,
                    '学历': job_degree,
                    '公司': c_name,
                    '公司领域': c_field_0,
                    '公司性质': c_field_1,
                    '公司规模': c_num
                }
                if not job_title:
                    skipped += 1
                    continue

                print(dit)
                resLs.append(dit)
            except Exception as e:
                skipped += 1
                print('解析单条失败，跳过：', e)

        if p != pz:
            try:
                driver.find_element(By.ID, 'jump_page').clear()
                driver.find_element(By.ID, 'jump_page').send_keys(p + 1)
                sleep(random.random())
                driver.find_element(By.CLASS_NAME, 'jumpPage').click()
            except Exception as e:
                print('翻页失败或未找到翻页控件：', e)

    # 所有页抓取完后再统一写入一次 CSV（避免多次重复写入）
    print(f'抓取完成，准备写入文件：共抓取 {len(resLs)} 条记录，跳过 {skipped} 条')
    if resLs:
        os.makedirs('data', exist_ok=True)
        pd.DataFrame(resLs).to_csv(f'data/{key}.csv', index=False, encoding='utf-8-sig')
        print(f'已写入 data/{key}.csv')
    else:
        print('未抓取到任何数据，未写入文件。请检查选择器或页面是否加载成功。')


if __name__ == '__main__':
    pz = 20
    for key in ['金融','财务']:
        options = ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        driver = webdriver.Chrome(options=options)
        # 优先尝试使用 python 包 selenium-stealth 来增强隐匿性（若已安装）
        stealth_used = False
        try:
            import importlib
            stealth_mod = importlib.import_module('selenium_stealth')
            stealth = getattr(stealth_mod, 'stealth', None)
            if stealth:
                try:
                    stealth(driver,
                            user_agent=None,
                            languages=["zh-CN", "zh"],
                            vendor="Google Inc.",
                            platform="Win32",
                            webgl_vendor="Intel Inc.",
                            renderer="ANGLE (Intel(R) Iris(TM) Graphics, OpenGL 4.1)",
                            fix_hairline=True)
                    stealth_used = True
                    print('已启用 selenium_stealth 以降低被检测风险')
                except Exception as e:
                    print('警告: selenium_stealth 可用但应用失败，错误:', e)
        except Exception:
            # selenium_stealth 未安装或导入失败，回退到检查本地 stealth.min.js
            pass

        if not stealth_used:
            js = None
            try:
                with open('stealth.min.js', 'r', encoding='utf-8') as _fj:
                    js = _fj.read()
            except FileNotFoundError:
                print("警告: stealth.min.js 未找到，未启用 stealth 注入。若需要请把该文件放在脚本同目录或安装 selenium-stealth。")
            except Exception as e:
                print('警告: 读取 stealth.min.js 发生错误，已跳过注入，错误:', e)

            if js:
                try:
                    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': js})
                    print('已从 stealth.min.js 注入 stealth 脚本')
                except Exception as e:
                    print('警告: 注入 stealth 脚本失败，继续执行，错误:', e)
        driver.get(f'https://we.51job.com/pc/search?keyword={key}&searchType=2&sortType=0&metro=')
        sleep(2)
        main()
        driver.quit()

# 数据入库

# 是否将抓取结果写入 MongoDB（默认关闭以避免在本地未运行 MongoDB 时导致脚本中断）
DO_DB_INSERT = False

import pymongo
import pandas as pd


def clearSalary(string):
    try:
        firstNum = string.split('-')[0]
        firstNum = eval(firstNum.strip('千万'))
        if '千' in string:
            num = firstNum * 1000
        elif '万' in string:
            num = firstNum * 10000
        if '年' in string:
            num /= 12
        return num
    except:
        return None


def clear(df):
    df['薪资'] = df['薪资'].apply(clearSalary)
    df.duplicated(keep='first')
    df.dropna(how='any', inplace=True)
    return df


def insert():
    # 读取 CSV（脚本现在将结果保存为 CSV）
    df = pd.read_csv(f'data/{key}.csv', encoding='utf-8-sig')
    df = clear(df)
    resLs = df.to_dict(orient='records')
    for res in resLs:
        res['key'] = key
        collection.insert_one(res)
        print(res)


if __name__ == '__main__':
    client = pymongo.MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
    db = client.test
    collection = db.job
    if DO_DB_INSERT:
        for key in ['金融','财务']:
            insert()
    else:
        print('DO_DB_INSERT = False，跳过 MongoDB 写入。如需启用请将 DO_DB_INSERT 设为 True 并确保 MongoDB 可用。')
