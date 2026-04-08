"""
简单的 DeepSeek API 测试脚本
用于验证配置是否正确，API 调用是否成功

2026/4/7 16:04 运行成功，测试无误
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 加载环境变量
load_dotenv()


def test_deepseek_connection():
    """测试 DeepSeek API 连接"""
    print("=" * 60)
    print("DeepSeek API 连接测试")
    print("=" * 60)
    
    # 读取配置
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    
    print(f"\n配置信息：")
    print(f"  Model: {model}")
    print(f"  Base URL: {base_url}")
    print(f"  API Key: {api_key[:20]}..." if api_key else "  API Key: 未配置")
    
    if not api_key:
        print("\n❌ 错误：LLM_API_KEY 未配置")
        return False
    
    try:
        print("\n正在初始化 ChatOpenAI 客户端...")
        llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=0.7,
            max_tokens=500,
        )
        
        print("正在发送测试消息...")
        messages = [
            SystemMessage(content="你是一个友好的助手，请用中文简短回复。"),
            HumanMessage(content="你好！请用一句话介绍你自己。"),
        ]
        
        response = llm.invoke(messages)
        
        print("\n✅ 测试成功！")
        print(f"\nDeepSeek 回复：\n{response.content}")
        print("\n" + "=" * 60)
        return True
        
    except Exception as exc:
        print(f"\n❌ 测试失败：{exc}")
        print("\n可能的原因：")
        print("  1. API Key 无效或已过期")
        print("  2. 网络连接问题")
        print("  3. DeepSeek API 服务暂时不可用")
        print("  4. Base URL 配置错误")
        print("\n" + "=" * 60)
        return False


def test_diary_analysis_prompt():
    """测试日记分析 Prompt"""
    print("\n" + "=" * 60)
    print("日记分析 Prompt 测试")
    print("=" * 60)
    
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    
    if not api_key:
        print("\n❌ 跳过：LLM_API_KEY 未配置")
        return False
    
    try:
        llm = ChatOpenAI(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=0.7,
            max_tokens=800,
        )
        
        # 模拟日记分析场景
        test_diary = """今天是开始新工作的第一天，心情有点紧张但也很兴奋。
早上起得特别早，认真准备了一下。到公司后，同事们都很友好，带我熟悉了环境。
虽然有很多新东西要学习，但我相信自己能够快速适应。"""
        
        messages = [
            SystemMessage(content="""你是一位温暖、积极的日记伴侣。你的任务是阅读用户的日记，
给出真诚、具体、鼓励性的评价。评价应该：
1. 肯定用户今天的记录和努力
2. 语气温暖、积极向上，像朋友一样
3. 长度控制在150-300字
4. 使用中文回复"""),
            HumanMessage(content=f"【今天的日记】\n{test_diary}\n\n请给出你的评价和鼓励："),
        ]
        
        print("\n正在生成 AI 分析...")
        response = llm.invoke(messages)
        
        print("\n✅ 分析生成成功！")
        print(f"\nAI 评价（{len(response.content)} 字）：")
        print("-" * 60)
        print(response.content)
        print("-" * 60)
        print("\n" + "=" * 60)
        return True
        
    except Exception as exc:
        print(f"\n❌ 测试失败：{exc}")
        print("\n" + "=" * 60)
        return False


if __name__ == "__main__":
    print("\n🚀 开始测试 DeepSeek API 集成...\n")
    
    # 测试 1：基础连接
    test1_passed = test_deepseek_connection()
    
    # 测试 2：日记分析 Prompt
    if test1_passed:
        test2_passed = test_diary_analysis_prompt()
        
        if test2_passed:
            print("\n✅ 所有测试通过！DeepSeek API 集成配置正确。")
        else:
            print("\n⚠️  基础连接成功，但日记分析测试失败。")
    else:
        print("\n❌ 基础连接测试失败，请检查配置。")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)