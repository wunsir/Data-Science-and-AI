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
import re


def _normalize_tag_tokens(value):
    """Normalize tag strings into a flat list of tokens."""
    if not value:
        return []
    if isinstance(value, str):
        raw_items = [value]
    else:
        raw_items = list(value)
    separators = (';', '；', '/', '|', ',', '，', '、')
    tokens = []
    for item in raw_items:
        if not item:
            continue
        text = item
        for sep in separators:
            text = text.replace(sep, ';')
        tokens.extend([seg.strip() for seg in text.split(';') if seg.strip()])
    return tokens


def _unique_preserve(seq):
    """Return list with duplicates removed while preserving order."""
    seen = set()
    result = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _clean_text_field(value):
    if isinstance(value, str):
        text = value.replace('\r', ' ').replace('\n', ' ')
        text = re.sub(r'\s{2,}', ' ', text)
        return text.strip()
    return value


def _wait_for_job_items(driver, base_wait=8, max_attempts=6):
    """Scrolls dynamically until job items become available or attempts exhausted."""
    total_scroll = 0
    for attempt in range(max_attempts):
        try:
            return WebDriverWait(driver, base_wait).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.joblist-item'))
            )
        except TimeoutException:
            driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
            sleep(0.6 + attempt * 0.3)
            total_scroll += 1
    return driver.find_elements(By.CSS_SELECTOR, '.joblist-item')


def main():
    resLs = []
    skipped = 0
    for p in range(pz):
        p += 1
        print(f'爬取第{p}页>>>')
        sleep(random.uniform(1.8, 3.2))
        items = _wait_for_job_items(driver)
        if not items:
            print('警告：职位列表长时间未加载，结果可能为空。')

        # 尝试直接使用浏览器 DOM（优先使用 sensorsdata 属性），回退到文本选择器
        if not items:
            try:
                os.makedirs('data', exist_ok=True)
                with open(f'data/{key}_last_page.html', 'w', encoding='utf-8') as _f:
                    _f.write(driver.page_source)
                print(f'警告：未找到任何 .joblist-item，已将页面源码保存到 data/{key}_last_page.html 以便调试')
            except Exception as _e:
                print('警告：尝试保存页面源码失败：', _e)
        for it in items:
            sleep(random.uniform(0.25, 0.7))
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
                # 额外字段：福利标签、技能标签、岗位描述
                welfare = ''
                jobtag = ''
                jobinfo = ''

                # 优先从 sensorsdata（若存在）中提取常见字段
                try:
                    if sensors and isinstance(info, dict):
                        # 灵活匹配可能的字段名
                        for k, v in info.items():
                            if not v:
                                continue
                            lk = k.lower()
                            if 'welf' in lk or 'benefit' in lk:
                                welfare = v
                            if 'jobinfo' in lk or 'description' in lk:
                                jobinfo = v
                            if 'tag' in lk or 'skill' in lk:
                                jobtag = v
                except Exception:
                    pass

                # 聚合标签并进行关键词分类
                welfare_keywords = (
                    '社保', '补充公积金', '绩效', '年假', '带薪', '五险一金', '补贴', '福利',
                    '不加班', '双休', '五险', '年终奖金', '定期体检', '过节费', '员工旅游', '出国机会',
                    '股票期权', '专业培训', '项目奖金', '节日津贴', '双休制', '健康体检', '年金', '六险二金',
                    '意外险', '年终奖', '餐补', '高底薪', '晋升空间', '高佣金', '提成', '降温取暖费', '做五休二',
                    '培训', '零食', '下午茶', '节日慰问', '免费班车', '宿舍', '弹性工作', '加班补助', '交通补助', '通讯补助',
                    '包吃', '包住', '食堂', '工装', '团队活动', '技术培训', '岗位晋升', '技能培训', '朝九晚五','补充医疗保险'
                )
                skill_keywords = (
                    '证券从业资格', '质量控制', '数据统计', '定期报告', '英语听说读写', 'cpa', '团队协同',
                    '投资顾问资格', '维护客户', 'java', '数据结构', '编程语言', '算法', '机器学习', '深度学习',
                    'pandas', 'tensorflow', 'numpy', '算法设计', 'matlab', 'cfa', 'wind', 'ifind', '行业研究',
                    '尽调', '管理咨询', 'python', 'sql', 'excel', 'powerpoint', 'office', 'tableau', 'power bi',
                    'sas', 'r语言', 'vba', '财务建模', '估值模型', 'dcf', 'lbo', '风险控制', '合规管理',
                    '财务分析', '成本控制', '税务筹划', '审计', '资产配置', '资产管理', '基金销售', '基金研究',
                    '量化分析', '回测', '统计分析', '风控模型', 'crm', '客户管理', '数据挖掘', '数据清洗',
                    '业务分析', '流程设计', '产品设计', '需求分析', '用户研究', '量化策略', 'mysql',
                    'sql server', 'hadoop', 'spark', 'etl', '数据可视化', '需求文档', 'prd', '敏捷开发',
                    'scrum', 'okr', 'kpi', '绩效管理', '团队管理', '商务沟通', '风控体系', '信用评估', 'abs',
                    '同业业务', '财务报表分析', '预算管理', '资金管理', '现金流预测', '内控', 'sox', '数据建模',
                    'bi报表', 'a/b测试', '用户运营', '增长黑客', '产品迭代', '需求评审', '流程梳理', '测试用例',
                    '自动化测试', 'saas', 'crm系统', 'erp', '业务协同', '项目管理','物理','建模','化学','工艺',
                    '设备维护','设备管理','生产管理','质量管理','安全管理','ai','大数据','云计算','区块链','运维','网络安全','保荐代表人'
                )
                description_keywords = (
                    '金融', '投资顾问', '证券', '银行', '理财顾问', '客户经理', '金融产品', '证券投资', '三会运作',
                    '投资', '证券事务', '投资并购', '一级市场', '股权投资', '上市公司', '销售', '营销', '机构销售',
                    '开发服务', '经管', 'pvc', '企业调研', '行业政策', '丙烯', '宏观经济数据', '挖掘投资机会',
                    '苯乙烯', '烧碱', '资产管理', '财富管理', '投融资', '融资租赁', '供应链金融', '资本市场',
                    '路演', '研究报告', '行业趋势', '市场推广', '客户开发', '渠道拓展', '绩效考核', '产品规划',
                    '用户增长', '运营策略', '活动策划', '营销推广', '客户服务', '风控合规', '投资策略',
                    '流程优化', '项目推进', '商业模式', '战略规划', '客户关系', '财富顾问', '私人银行',
                    '家族信托', '并购重组', 'ipo', '二级市场', '量化交易', '宏观研究', '策略研究', '买方研究',
                    '卖方研究', '行业分析', '财务尽调', '风险排查', '路演材料', '股东大会', '董事会', '项目落地',
                    '跨部门协作', '活动执行', '品牌推广', '数据驱动', '精细化运营','私募'
                )

                welfare_keywords_lower = tuple(w.lower() for w in welfare_keywords)
                skill_keywords_lower = tuple(s.lower() for s in skill_keywords)
                description_keywords_lower = tuple(d.lower() for d in description_keywords)

                dom_tags = []
                try:
                    for t in it.find_elements(By.CSS_SELECTOR, '.tag-list span, .joblist-item-job .tag-list span, .label, .tag'):
                        try:
                            txt = t.text.strip()
                            if txt:
                                dom_tags.append(txt)
                        except Exception:
                            continue
                except Exception:
                    dom_tags = []

                welfare_tokens = _normalize_tag_tokens(welfare)
                skill_tokens = _normalize_tag_tokens(jobtag)
                desc_additions = []

                for token in _normalize_tag_tokens(dom_tags):
                    token_lower = token.lower()
                    if any(w in token_lower for w in welfare_keywords_lower):
                        welfare_tokens.append(token)
                    elif any(s in token_lower for s in skill_keywords_lower):
                        skill_tokens.append(token)
                    elif any(d in token_lower for d in description_keywords_lower):
                        desc_additions.append(token)
                    else:
                        skill_tokens.append(token)

                # 确保技能关键词从岗位描述中也被识别
                if jobinfo:
                    jobinfo_lower = jobinfo.lower()
                    for kw in skill_keywords:
                        if kw.lower() in jobinfo_lower and kw not in skill_tokens:
                            skill_tokens.append(kw)

                filtered_skill_tokens = []
                for token in skill_tokens:
                    token_lower = token.lower()
                    if any(d in token_lower for d in description_keywords_lower) and not any(s in token_lower for s in skill_keywords_lower):
                        desc_additions.append(token)
                    else:
                        filtered_skill_tokens.append(token)

                welfare_tokens = _unique_preserve(welfare_tokens)
                filtered_skill_tokens = _unique_preserve(filtered_skill_tokens)
                desc_additions = _unique_preserve(desc_additions)

                if welfare_tokens:
                    welfare = ';'.join(welfare_tokens)
                if filtered_skill_tokens:
                    jobtag = ';'.join(filtered_skill_tokens)

                if desc_additions:
                    for token in desc_additions:
                        if not token:
                            continue
                        if jobinfo and token in jobinfo:
                            continue
                        jobinfo = f"{jobinfo}\n{token}" if jobinfo else token

                # 如果仍然没有岗位描述，尝试打开详情页抓取（尽量在单独 tab 打开，随后关闭）
                if not jobinfo:
                    try:
                        href = None
                        try:
                            a = it.find_element(By.CSS_SELECTOR, 'a.jname, a.jname.text-cut, .jname a')
                            href = a.get_attribute('href')
                        except Exception:
                            href = None

                        if href:
                            original_handle = driver.current_window_handle
                            driver.execute_script('window.open(arguments[0]);', href)
                            driver.switch_to.window(driver.window_handles[-1])
                            # 等待详情主要容器出现，放宽到多个可能的选择器
                            try:
                                WebDriverWait(driver, 8).until(
                                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.job-detail, .bmsg, #job_msg, .job_msg'))
                                )
                            except Exception:
                                pass
                            page_html = driver.page_source
                            try:
                                tree = etree.HTML(page_html)
                                # 尝试多个 xpath 来获取更完整的描述文本
                                candidates = []
                                for xp in ['//div[contains(@class,"job-detail")]//text()', '//div[contains(@class,"bmsg")]//text()', '//div[@id="job_msg"]//text()', '//div[contains(@class,"job_msg")]//text()']:
                                    texts = tree.xpath(xp)
                                    if texts:
                                        txt = '\n'.join([t.strip() for t in texts if t.strip()])
                                        if txt:
                                            candidates.append(txt)
                                if candidates:
                                    # 取最长的文本作为岗位描述
                                    jobinfo = max(candidates, key=len)
                            except Exception:
                                pass
                            # 关闭详情页，切回原 tab
                            try:
                                driver.close()
                            except Exception:
                                pass
                            driver.switch_to.window(original_handle)
                    except Exception:
                        pass

                dit['福利标签'] = welfare
                dit['技能标签'] = jobtag
                dit['岗位描述'] = jobinfo
                dit = {k: _clean_text_field(v) for k, v in dit.items()}
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
                if random.random() < 0.15:
                    pause = random.uniform(4, 8)
                    print(f'长暂停 {pause:.1f} 秒以降低触发风险...')
                    sleep(pause)
            except Exception as e:
                print('翻页失败或未找到翻页控件：', e)
        else:
            if random.random() < 0.12:
                pause = random.uniform(4, 7)
                print(f'分页结束，休息 {pause:.1f} 秒...')
                sleep(pause)

    # 所有页抓取完后再统一写入一次 CSV（避免多次重复写入）
    print(f'抓取完成，准备写入文件：共抓取 {len(resLs)} 条记录，跳过 {skipped} 条')
    if resLs:
        output_dir = '/Users/catherine/Desktop/vscode/爬虫上传/finding_jobs/qianchengwuyou/data'
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f'{key}.csv')
        pd.DataFrame(resLs).to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f'已写入 {output_path}')
    else:
        print('未抓取到任何数据，未写入文件。请检查选择器或页面是否加载成功。')


if __name__ == '__main__':
    pz = 50
    for key in ['产品','运营']:
    #['证券研究所','投行','保险','银行','财务','基金经理','数据分析','产品','运营']:
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
    client = pymongo.MongoClient('mongodb://root:abc_123456@localhost:27017')
    db = client.test
    collection = db.job
    if DO_DB_INSERT:
        for key in ['产品','运营']:
        #['证券研究所','投行','保险','银行','财务','基金经理','数据分析','产品','运营']:
        #for key in ['运营']:
            insert()
    else:
        print('DO_DB_INSERT = False，跳过 MongoDB 写入。如需启用请将 DO_DB_INSERT 设为 True 并确保 MongoDB 可用。')
