import os
import time
import subprocess
import psutil
from playwright.sync_api import sync_playwright
from pathlib import Path
from Lib.config import config

output_dir = './out'
os.makedirs(output_dir, exist_ok=True)
default_edge_path = Path("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe")
make_edge_happy = False

def count_words(line):
    # 统计一行中的词数，以空格分隔
    return len(line.split())

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    total_word_count = 0
    strings_array = []
    current_string = []
    
    for i, line in enumerate(lines):
        line = line.strip()  # 去掉行首尾的空白字符
        line_word_count = count_words(line)
        total_word_count += line_word_count
        
        current_string.append(line)  # 添加当前行到当前字符串中
        
        if total_word_count > 150:
            # 当前字符串超过1000词，截断并保存
            strings_array.append('\n'.join(current_string))
            # 重置统计
            total_word_count = 0
            current_string = []
    
    # 添加最后一部分（如果有剩余）
    if current_string:
        strings_array.append('\n'.join(current_string))
    
    return strings_array

def initialize_edge(disable_user_profile):
    # 结束现有edge进程
    print("正在尝试结束现有edge示例...")
    for proc in psutil.process_iter():
        try:
            if proc.name().lower() == "msedge.exe":
                proc.terminate()
                proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    if not disable_user_profile:
        # 构建 Edge 默认用户数据目录路径
        print("正在构建带用户数据的调试模式edge...")
        username = os.getlogin()
        if os.name == 'nt':  # Windows
            user_data_dir = fr"C:\Users\{username}\AppData\Local\Microsoft\Edge\User Data"
        elif os.name == 'posix':  # macOS/Linux
            if 'darwin' in os.uname().sysname.lower():  # macOS
                user_data_dir = f"/Users/{username}/Library/Application Support/Microsoft Edge"
            else:  # Linux
                user_data_dir = f"/home/{username}/.config/microsoft-edge"
        else:
            raise OSError("Unsupported operating system")
        if not os.path.exists(user_data_dir):
            print(f"用户数据目录不存在: {user_data_dir}")
            user_data_dir = None
        if user_data_dir:
            subprocess.Popen([default_edge_path, '--remote-debugging-port=9222', f'--user-data-dir={user_data_dir}'], shell = True)
        else:
            subprocess.Popen([default_edge_path, '--remote-debugging-port=9222'], shell = True)
    else:
        subprocess.Popen([default_edge_path, '--remote-debugging-port=9222', '--inprivate'], shell = True)
        print("正在拉起不带用户数据的edge")


def force_select(page, source_lang, target_lang):
    print("尝试强制指定源语言\n如果卡在此处可能需要手动点击一下源语言选择")
    try:
        page.wait_for_selector('span[data-testid="translator-source-lang"]')
        page.click('span[data-testid="translator-source-lang"]')

        # 使用 XPath 选择器
        lang_xpath = f'//button[@data-testid="translator-lang-option-{source_lang}"]'
        page.wait_for_selector(lang_xpath)
        page.click(lang_xpath)

        print(f"已强制指定源语言{source_lang}")
    except Exception as e:
        print(f"设置源语言时发生错误: {e}")
    print("尝试强制指定目标语言\n如果卡在此处可能需要手动点击一下目标语言选择")
    try:
        # 点击目标语言选择区域
        page.wait_for_selector('div[data-testid="translator-target-lang"]')
        page.click('div[data-testid="translator-target-lang"]')

        # 使用 XPath 选择器
        lang_xpath = f'//button[@data-testid="translator-lang-option-{target_lang}"]'
        page.wait_for_selector(lang_xpath)
        page.click(lang_xpath)

        print(f"已强制指定目标语言{target_lang}")
    except Exception as e:
        print(f"设置目标语言时发生错误: {e}")

def translate_text(page, text, source_lang, target_lang, force_lang_select):
    global make_edge_happy
    # 使用CSS选择器定位输入框元素
    input_element = page.query_selector('div[contenteditable="true"][role="textbox"][aria-multiline="true"]')
    #print(text)

    if input_element:
        input_element.fill('')  # 清空输入框
        input_element.fill(text)
    else:
        print("输入框元素未找到")
        return None
    if force_lang_select:
        force_select(page, source_lang, target_lang)

    time.sleep(1)

    # 使用wait_for_selector方法等待翻译结果出现
    output_element = page.wait_for_selector('section[aria-labelledby="translation-target-heading"] div[contenteditable="true"][role="textbox"][aria-multiline="true"]')

    if output_element:
        original_lines = len(text.split('\n'))+1
        retry_count = 0 
        while True:
            time.sleep(1)  # 每秒检查一次
            translated_text = output_element.inner_text()
            #print(f"原译文{translated_text}")
            
            #edge浏览器得到的返回内容和webkit不一样
            if make_edge_happy:
                translated_lines = translated_text.splitlines()
                processed_result = []
                empty_line_count = 0  
                for line in translated_lines:
                    if line.strip() == "":  
                        empty_line_count += 1
                        if empty_line_count == 3:
                            processed_result.append("")  # 添加一个空行
                    else:
                        empty_line_count = 0
                        processed_result.append(line)  # 添加非空行
                
                # 将处理后的结果合并成字符串
                translated_text = "\n".join(processed_result) + "\n"
                #print(f"处理后译文{translated_text}")
                translated_lines = len(translated_text.split('\n'))
            else:
                translated_lines = len(translated_text.split('\n'))
            print(f"已翻译{translated_lines}/{original_lines}行")
            if translated_lines == original_lines:
                return translated_text
            retry_count += 1
            if retry_count >= 10:
                print("翻译行数不匹配，刷新网页重试")
                page.reload()  # 刷新网页
                retry_count = 0  # 重置重试计数器
                
                # 重新定位输入框元素
                input_element = page.query_selector('div[contenteditable="true"][role="textbox"][aria-multiline="true"]')
                if input_element:
                    input_element.fill('')  # 清空输入框
                    input_element.fill(text)
                else:
                    print("输入框元素未找到")
                    return None
                
                # 重新定位输出框元素
                output_element = page.wait_for_selector('section[aria-labelledby="translation-target-heading"] div[contenteditable="true"][role="textbox"][aria-multiline="true"]')
                if not output_element:
                    print("翻译结果元素未找到")
                    return None
    else:
        print("翻译结果元素未找到")
        return None

def playwright_engine(
    source_lang, target_lang, force_lang_select, 
    browser_login, disable_user_profile, 
    playwright_headless, playwright_path, input_file_path = 'text_extracted.txt'
    ):
    global make_edge_happy
    if browser_login or not Path(playwright_path).exists():
        initialize_edge(disable_user_profile)
    strings_array = process_file(input_file_path)
    output_file_path = os.path.join(output_dir, 'translated_result.txt')
    
    with sync_playwright() as p:
        # Launch the browser
        print("正在拉起浏览器")
        if Path(playwright_path).exists() and not browser_login:
            browser_executable_path = Path(playwright_path)
            browser = p.webkit.launch(executable_path=browser_executable_path, headless=playwright_headless)
            make_edge_happy = False
            page = browser.new_page()
        elif default_edge_path.exists():
            print("正在使用edge内核，但该模式可能兼容性有问题")
            browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')  # 连接到远程调试端口
            context = browser.contexts[0]  # 获取已有的上下文
            page = context.pages[0]
            make_edge_happy = True
        else:
            raise FileNotFoundError("找不到Playwright内核")
        
        page.goto(f"https://www.deepl.com/translator#{source_lang}/{target_lang}/")
        
        with open(output_file_path, 'w', encoding='utf-8') as result_file:
            for i, s in enumerate(strings_array):
                translation = translate_text(page, s, source_lang, target_lang, force_lang_select)
                if translation:
                    print(f"写入翻译结果 {i + 1}, 正在尝试下一个资源段翻译")
                    result_file.write(translation)
        
        browser.close()
