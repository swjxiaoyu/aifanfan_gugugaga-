"""
爱番番寻客宝 RPA (增加字段版 - 注册资本/日期/行业)
注意：电话号码提取逻辑完全保持原版不动
"""

import time
import random
import csv
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions
# 引入按键映射，用于按 ESC
from DrissionPage.common import Keys

# ============ 1. 选择器配置 ============
SELECTORS = {
    # 每一行企业卡片
    'company_card': 'tag:tr@@class:el-table__row',

    # 公司名
    'company_name': '.company-name',

    # --- 新增/修改的字段定位符 ---
    # 逻辑：DrissionPage 可以通过文本定位元素，再找它的下一个兄弟节点
    'label_legal': 'text:法人代表',
    'label_capital': 'text:注册资本', # 新增
    'label_date': 'text:成立日期',    # 新增
    'label_industry': 'text:行业',    # 新增

    # 电话按钮
    'phone_btn': 'tag:button@@class:contact-btn',

    # 详情页的电话条目容器
    'contact_item': '.contact-item',

    # 详情页里的电话文本 class
    'phone_text': '.text.f-1',

    # 下一页按钮
    'next_page_btn': 'text:下一页',
}

# CSV 配置 (已添加新字段)
OUTPUT_FILE = 'company_data_extended.csv'
CSV_HEADERS = ['公司名', '法人代表', '注册资本', '成立日期', '行业', '手机号列表']


# ============ 2. 初始化 ============

def init_browser():
    options = ChromiumOptions()
    options.set_user_data_path('user_data')
    options.set_argument('--ignore-certificate-errors')
    return ChromiumPage(options)


def init_csv_file():
    if not Path(OUTPUT_FILE).exists():
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            csv.DictWriter(f, fieldnames=CSV_HEADERS).writeheader()


def wait_for_manual_login():
    print("\n" + "=" * 60)
    print("📢 请在浏览器手动登录，搜索关键词，并确保有数据列表。")
    print("📢 准备好后，请按回车继续...")
    print("=" * 60)
    input()


# ============ 3. 数据提取 (保持电话逻辑不动) ============

def extract_company_name(row_element):
    """在当前行(tr)中查找公司名"""
    try:
        ele = row_element.ele(SELECTORS['company_name'], timeout=1)
        return ele.text.strip() if ele else '未获取'
    except:
        return '未获取'


def extract_by_label(row_element, label_selector):
    """
    【新增】通用提取函数：
    用于提取 法人、注册资本、成立日期、行业
    原理：找到包含特定文本的标签，取其下一个兄弟节点的文本
    """
    try:
        # timeout设置短一点，提高效率
        label = row_element.ele(label_selector, timeout=0.2)
        if label:
            content = label.next(timeout=0.2)
            return content.text.strip() if content else ''
        return ''
    except:
        return ''


def extract_phone_numbers(page, row_element):
    """
    点击按钮 -> 等待可拨通联系人项出现 -> 提取号码 -> ESC关闭 -> 等待2秒继续
    """
    try:
        # 1. 关闭可能残留的抽屉
        page.actions.type(Keys.ESCAPE)
        time.sleep(0.3)

        # 2. 查找并点击按钮
        phone_btn = row_element.ele(SELECTORS['phone_btn'], timeout=2)
        if not phone_btn:
            print("  [跳过] 未找到极速联系按钮")
            return '无号码'

        phone_btn.scroll.to_see()
        time.sleep(0.5)
        phone_btn.click()
        print("  [点击] 极速联系按钮")

        # 3. 等待可拨通联系人项出现（XPath筛选）
        items = None
        start_time = time.time()
        timeout_items = 8
        xpath_available = 'xpath://div[contains(@class, "contact-item")][.//span[text()="可拨通"]]'
        while time.time() - start_time < timeout_items:
            items = page.eles(xpath_available)
            if items:
                print(f"  [成功] 找到 {len(items)} 个可拨通联系人项")
                break
            time.sleep(0.5)
        else:
            print("  [警告] 未找到可拨通联系人项")
            all_items = page.eles(SELECTORS['contact_item'])
            if all_items:
                print(f"  [调试] 共有 {len(all_items)} 个联系人项，但无可拨通标签")
            page.actions.type(Keys.ESCAPE)
            return '无可拨通项'

        # 4. 提取号码（多种方式尝试）
        phone_list = []
        for idx, item in enumerate(items):
            try:
                # 尝试多种方式提取电话号码
                p_ele = None
                
                # 方式1：原选择器 .text.f-1
                p_ele = item.ele(SELECTORS['phone_text'], timeout=0.5)
                
                # 方式2：严格类名匹配
                if not p_ele:
                    p_ele = item.ele('tag:span@@class=text f-1', timeout=0.5)
                
                # 方式3：XPath 包含类名
                if not p_ele:
                    p_ele = item.ele('xpath:.//span[contains(@class,"text") and contains(@class,"f-1")]', timeout=0.5)
                
                # 方式4：只根据类名中的 text 定位
                if not p_ele:
                    p_ele = item.ele('.text', timeout=0.5)
                
                if p_ele:
                    txt = p_ele.text.strip()
                    if txt and txt not in phone_list:
                        phone_list.append(txt)
                        print(f"    -> 可拨通号码 {idx+1}: {txt}")
                else:
                    print(f"    [注意] 可拨通项 {idx+1} 未找到电话号码（所有方式失败）")
                    # 调试：打印该项的部分HTML（前200字符）
                    html_snippet = item.html[:200] if item.html else "无HTML"
                    print(f"        该项HTML片段: {html_snippet}")
            except Exception as e:
                print(f"    [异常] 可拨通项 {idx+1}: {e}")
                continue

        result = ' | '.join(phone_list) if phone_list else '无可拨通号码'
        print(f"  [完成] 共提取 {len(phone_list)} 个可拨通号码")

        # 5. 关闭抽屉（ESC）并等待4秒（不等待抽屉消失）
        time.sleep(0.5)
        print("  [操作] 按 ESC 关闭抽屉...")
        page.actions.type(Keys.ESCAPE)
        print("  [操作] ESC 已按下，等待4秒后继续...")
        time.sleep(4)  # 固定等待4秒，无论抽屉是否消失

        return result

    except Exception as e:
        print(f"  [错误] 电话流程异常: {e}")
        try:
            page.actions.type(Keys.ESCAPE)
        except:
            pass
        return '异常'


def save_to_csv(data):
    try:
        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8-sig') as f:
            csv.DictWriter(f, fieldnames=CSV_HEADERS).writerow(data)
    except Exception as e:
        print(f"写入CSV失败: {e}")


# ============ 4. 主逻辑 ============

def process_page(page, page_num):
    # 获取所有的表格行 (tr)
    rows = page.eles(SELECTORS['company_card'])
    
    if not rows:
        print("未找到数据行，请检查页面是否加载完成。")
        return 0

    print(f"\n>>> 第 {page_num} 页，发现 {len(rows)} 行数据")

    count = 0
    for i, row in enumerate(rows):
        print(f"\n[第 {page_num} 页 - 第 {i+1} 行]")
        
        # --- 1. 提取基础信息 (新增了三个字段) ---
        c_name = extract_company_name(row)
        c_legal = extract_by_label(row, SELECTORS['label_legal'])
        c_capital = extract_by_label(row, SELECTORS['label_capital'])
        c_date = extract_by_label(row, SELECTORS['label_date'])
        c_industry = extract_by_label(row, SELECTORS['label_industry'])
        
        # 终端打印增加显示
        print(f"  公司: {c_name}")
        print(f"  详情: 法人[{c_legal}] | 资本[{c_capital}] | 日期[{c_date}] | 行业[{c_industry}]")

        # --- 2. 提取电话 (原逻辑) ---
        c_phone = extract_phone_numbers(page, row)

        # --- 3. 保存 (新增了三个字段) ---
        save_to_csv({
            '公司名': c_name,
            '法人代表': c_legal,
            '注册资本': c_capital,
            '成立日期': c_date,
            '行业': c_industry,
            '手机号列表': c_phone
        })
        count += 1

    return count


def main():
    page = init_browser()
    init_csv_file()
    wait_for_manual_login()

    page_num = 1
    while True:
        count = process_page(page, page_num)
        if count == 0:
            print("当前页无数据，停止。")
            break
        
        # 翻页逻辑
        next_btn = page.ele(SELECTORS['next_page_btn'])
        
        if not next_btn or \
           next_btn.attr('disabled') is not None or \
           'disabled' in (next_btn.attr('class') or ''):
            print("\n已到达最后一页。")
            break

        print("\n[翻页] 点击下一页...")
        next_btn.click()
        wait_s = random.uniform(5, 8)
        print(f"等待 {wait_s} 秒...")
        time.sleep(wait_s)
        
        page_num += 1

    print("任务完成。")

if __name__ == '__main__':
    main()