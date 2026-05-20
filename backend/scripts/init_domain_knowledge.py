"""
Domain Knowledge Store 初始化脚本
==================================

将 50-100 条精选心理学知识写入 Chroma 共享集合 "domain_knowledge_psychology"。

覆盖领域：
1. CBT（认知行为疗法）基础 — 认知扭曲识别、思维记录、行为实验
2. 正念技巧 — 呼吸练习、身体扫描、正念冥想
3. 睡眠卫生 — 睡眠习惯、环境优化、认知策略
4. 社会支持理论 — 社交网络、求助行为、人际关系维护
5. 情绪调节策略 — 情绪识别、调节技巧、压力管理

使用方式：
    cd backend
    python -m scripts.init_domain_knowledge

    或直接运行：
    python scripts/init_domain_knowledge.py

注意：
- 此脚本可重复运行（使用 upsert），不会产生重复数据
- 需要 Embedding 模型已下载到本地
- 运行前确保 CHROMA_PERSIST_DIR 环境变量正确设置
"""

import os
import sys
import logging

# 确保可以导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════════╗
# ║  精选心理学知识条目                                            ║
# ╚══════════════════════════════════════════════════════════════╝

DOMAIN_KNOWLEDGE_ENTRIES = [
    # ═══════════════════════════════════════════════════════════
    # CBT（认知行为疗法）基础 — 20 条
    # ═══════════════════════════════════════════════════════════
    {
        "id": "cbt_001",
        "content": "认知行为疗法（CBT）的核心原理：我们的想法（认知）影响我们的感受（情绪）和行为。通过识别和改变不合理的思维模式，可以改善情绪状态和行为反应。",
        "category": "cbt",
        "topic": "CBT核心原理",
        "source": "Beck, J.S. (2011). Cognitive Behavior Therapy: Basics and Beyond",
    },
    {
        "id": "cbt_002",
        "content": "常见认知扭曲——全或无思维：用非黑即白的方式看待事物，没有中间地带。例如'如果我做不到完美，那就是彻底失败'。识别这种思维模式是改变的第一步。",
        "category": "cbt",
        "topic": "认知扭曲-全或无思维",
        "source": "Burns, D.D. (1980). Feeling Good: The New Mood Therapy",
    },
    {
        "id": "cbt_003",
        "content": "常见认知扭曲——灾难化思维：总是预期最坏的结果会发生。应对方法：问自己'最坏的情况真的会发生吗？即使发生了，我能应对吗？最可能的结果是什么？'",
        "category": "cbt",
        "topic": "认知扭曲-灾难化",
        "source": "Burns, D.D. (1980). Feeling Good: The New Mood Therapy",
    },
    {
        "id": "cbt_004",
        "content": "常见认知扭曲——过度概括：从单一事件得出普遍性结论。例如一次面试失败就认为'我永远找不到工作'。可以用具体证据来检验这个结论是否成立。",
        "category": "cbt",
        "topic": "认知扭曲-过度概括",
        "source": "Burns, D.D. (1980). Feeling Good: The New Mood Therapy",
    },
    {
        "id": "cbt_005",
        "content": "思维记录法：当感到情绪低落时，记录下触发事件、自动化思维、情绪反应和强度（0-100）。然后寻找支持和反对该想法的证据，最后形成更平衡的替代想法。",
        "category": "cbt",
        "topic": "思维记录技术",
        "source": "Greenberger, D. & Padesky, C.A. (2015). Mind Over Mood",
    },
    {
        "id": "cbt_006",
        "content": "行为激活：当情绪低落时，人们倾向于减少活动，这会形成恶性循环。有意识地安排愉悦活动和成就感活动，即使不想做也先行动，情绪往往会随之改善。",
        "category": "cbt",
        "topic": "行为激活",
        "source": "Martell, C.R. et al. (2010). Behavioral Activation for Depression",
    },
    {
        "id": "cbt_007",
        "content": "认知重构三步法：1）识别自动化消极思维；2）评估该想法的证据（支持和反对）；3）形成更现实、更平衡的替代想法。这不是'积极思考'，而是'现实思考'。",
        "category": "cbt",
        "topic": "认知重构",
        "source": "Beck, J.S. (2011). Cognitive Behavior Therapy: Basics and Beyond",
    },
    {
        "id": "cbt_008",
        "content": "常见认知扭曲——心理过滤：只关注负面细节而忽略正面信息。例如收到十条好评和一条差评，却只记住差评。练习有意识地注意和记录积极事件可以平衡这种倾向。",
        "category": "cbt",
        "topic": "认知扭曲-心理过滤",
        "source": "Burns, D.D. (1980). Feeling Good: The New Mood Therapy",
    },
    {
        "id": "cbt_009",
        "content": "常见认知扭曲——应该思维：用'应该''必须'来要求自己或他人。这会产生内疚、愤怒和挫败感。尝试将'应该'替换为'我希望'或'如果能...会更好'。",
        "category": "cbt",
        "topic": "认知扭曲-应该思维",
        "source": "Ellis, A. (1962). Reason and Emotion in Psychotherapy",
    },
    {
        "id": "cbt_010",
        "content": "暴露疗法原理：逐步面对引起焦虑的情境，从低焦虑到高焦虑循序渐进。每次暴露后焦虑会自然下降（习惯化），反复练习后对该情境的恐惧会显著减少。",
        "category": "cbt",
        "topic": "暴露疗法",
        "source": "Foa, E.B. & Kozak, M.J. (1986). Emotional Processing of Fear",
    },
    {
        "id": "cbt_011",
        "content": "苏格拉底式提问：通过自我提问来检验想法的合理性。常用问题：'支持这个想法的证据是什么？''有没有其他解释？''如果朋友遇到同样情况，我会怎么建议他？'",
        "category": "cbt",
        "topic": "苏格拉底式提问",
        "source": "Beck, J.S. (2011). Cognitive Behavior Therapy: Basics and Beyond",
    },
    {
        "id": "cbt_012",
        "content": "常见认知扭曲——个人化：把不完全由自己控制的事情归咎于自己。例如'孩子成绩不好一定是我的错'。区分自己的责任和他人/环境的因素，有助于减轻不必要的自责。",
        "category": "cbt",
        "topic": "认知扭曲-个人化",
        "source": "Burns, D.D. (1980). Feeling Good: The New Mood Therapy",
    },
    {
        "id": "cbt_013",
        "content": "行为实验：当你有一个消极预测时（如'如果我拒绝别人，他们会讨厌我'），设计一个小实验来检验它。记录预测、实际结果和从中学到的东西。",
        "category": "cbt",
        "topic": "行为实验",
        "source": "Bennett-Levy, J. et al. (2004). Oxford Guide to Behavioural Experiments",
    },
    {
        "id": "cbt_014",
        "content": "情绪温度计：用0-100分来评估情绪强度。0分表示完全没有该情绪，100分表示最强烈。定期记录情绪温度可以帮助识别情绪变化的模式和触发因素。",
        "category": "cbt",
        "topic": "情绪监测",
        "source": "Greenberger, D. & Padesky, C.A. (2015). Mind Over Mood",
    },
    {
        "id": "cbt_015",
        "content": "常见认知扭曲——读心术：假设自己知道别人在想什么，通常是负面的。例如'他一定觉得我很无聊'。提醒自己：我们无法真正知道别人的想法，除非直接沟通确认。",
        "category": "cbt",
        "topic": "认知扭曲-读心术",
        "source": "Burns, D.D. (1980). Feeling Good: The New Mood Therapy",
    },
    {
        "id": "cbt_016",
        "content": "问题解决疗法五步法：1）明确定义问题；2）头脑风暴所有可能的解决方案（不评判）；3）评估每个方案的优缺点；4）选择最佳方案并制定行动计划；5）执行后评估效果。",
        "category": "cbt",
        "topic": "问题解决",
        "source": "D'Zurilla, T.J. & Nezu, A.M. (2007). Problem-Solving Therapy",
    },
    {
        "id": "cbt_017",
        "content": "活动日程安排：将每天分为若干时间段，提前安排愉悦活动（P）和掌控感活动（M）。完成后评估实际的愉悦度和掌控感（0-10分），帮助发现哪些活动真正改善心情。",
        "category": "cbt",
        "topic": "活动安排",
        "source": "Martell, C.R. et al. (2010). Behavioral Activation for Depression",
    },
    {
        "id": "cbt_018",
        "content": "常见认知扭曲——贴标签：给自己或他人贴上全面否定的标签。例如犯了一个错误就说'我是个失败者'。将行为与身份分开：'我犯了一个错误'不等于'我是个失败者'。",
        "category": "cbt",
        "topic": "认知扭曲-贴标签",
        "source": "Burns, D.D. (1980). Feeling Good: The New Mood Therapy",
    },
    {
        "id": "cbt_019",
        "content": "渐进式肌肉放松：系统地紧张和放松身体各肌肉群。从脚趾开始，紧张5秒后放松15秒，逐步向上到头部。这有助于降低身体紧张水平，缓解焦虑和压力。",
        "category": "cbt",
        "topic": "放松技术",
        "source": "Jacobson, E. (1938). Progressive Relaxation",
    },
    {
        "id": "cbt_020",
        "content": "担忧时间技术：每天设定固定的15-30分钟'担忧时间'。当担忧出现在其他时间时，记下来并告诉自己'我会在担忧时间处理它'。这有助于控制反刍思维，减少全天候的焦虑。",
        "category": "cbt",
        "topic": "担忧管理",
        "source": "Borkovec, T.D. et al. (1983). Stimulus Control of Worrying",
    },

    # ═══════════════════════════════════════════════════════════
    # 正念技巧 — 15 条
    # ═══════════════════════════════════════════════════════════
    {
        "id": "mindfulness_001",
        "content": "正念呼吸练习：找一个舒适的姿势，将注意力集中在呼吸上。注意空气进出鼻腔的感觉，腹部的起伏。当注意力游走时，温和地将它带回呼吸。每天练习5-10分钟即可见效。",
        "category": "mindfulness",
        "topic": "正念呼吸",
        "source": "Kabat-Zinn, J. (1990). Full Catastrophe Living",
    },
    {
        "id": "mindfulness_002",
        "content": "身体扫描冥想：从头顶开始，逐步将注意力移向身体各部位，注意每个部位的感觉（温度、紧张、放松）。不试图改变任何感觉，只是观察。这有助于增强身体觉察和放松。",
        "category": "mindfulness",
        "topic": "身体扫描",
        "source": "Kabat-Zinn, J. (1990). Full Catastrophe Living",
    },
    {
        "id": "mindfulness_003",
        "content": "正念的核心态度：不评判——对当下体验保持开放和好奇，不急于贴上'好'或'坏'的标签。像一个友善的观察者一样看待自己的想法和感受，而不是与之对抗。",
        "category": "mindfulness",
        "topic": "正念态度",
        "source": "Kabat-Zinn, J. (2003). Mindfulness-Based Interventions in Context",
    },
    {
        "id": "mindfulness_004",
        "content": "5-4-3-2-1 接地技术：当感到焦虑或恐慌时，注意5样你能看到的东西、4样你能触摸的、3样你能听到的、2样你能闻到的、1样你能尝到的。这能快速将注意力拉回当下。",
        "category": "mindfulness",
        "topic": "接地技术",
        "source": "Teasdale, J.D. et al. (2014). The Mindful Way Workbook",
    },
    {
        "id": "mindfulness_005",
        "content": "正念行走：以比平时慢的速度行走，注意脚底接触地面的感觉、腿部肌肉的运动、身体重心的转移。这是一种将正念融入日常活动的简单方法，不需要额外时间。",
        "category": "mindfulness",
        "topic": "正念行走",
        "source": "Thich Nhat Hanh (1991). Peace Is Every Step",
    },
    {
        "id": "mindfulness_006",
        "content": "RAIN 技术处理困难情绪：R(Recognize)识别情绪；A(Allow)允许它存在；I(Investigate)好奇地探索它在身体中的感觉；N(Non-identification)不与情绪认同——'我有愤怒'而非'我是愤怒的'。",
        "category": "mindfulness",
        "topic": "RAIN技术",
        "source": "Brach, T. (2013). True Refuge",
    },
    {
        "id": "mindfulness_007",
        "content": "正念饮食：吃饭时放下手机，注意食物的颜色、气味、质地和味道。慢慢咀嚼，感受食物在口中的变化。这不仅能增加进食的愉悦感，还有助于控制食量和改善消化。",
        "category": "mindfulness",
        "topic": "正念饮食",
        "source": "Bays, J.C. (2009). Mindful Eating",
    },
    {
        "id": "mindfulness_008",
        "content": "思维观察练习：想象你的思维是天空中飘过的云朵，或是河流中漂过的树叶。你只是坐在河边观察它们经过，不需要抓住任何一片叶子。思维来了又走，这是自然的。",
        "category": "mindfulness",
        "topic": "思维观察",
        "source": "Harris, R. (2008). The Happiness Trap",
    },
    {
        "id": "mindfulness_009",
        "content": "三分钟呼吸空间：1）第一分钟：觉察当下的想法、感受和身体感觉；2）第二分钟：将注意力集中到呼吸上；3）第三分钟：将觉察扩展到整个身体。适合在忙碌中快速重置。",
        "category": "mindfulness",
        "topic": "呼吸空间",
        "source": "Segal, Z.V. et al. (2013). Mindfulness-Based Cognitive Therapy",
    },
    {
        "id": "mindfulness_010",
        "content": "自我慈悲三要素：1）善待自己——像对待好朋友一样对待自己；2）共通人性——认识到痛苦和不完美是人类共同的经历；3）正念——平衡地觉察痛苦，不过度认同也不压抑。",
        "category": "mindfulness",
        "topic": "自我慈悲",
        "source": "Neff, K. (2011). Self-Compassion: The Proven Power of Being Kind to Yourself",
    },
    {
        "id": "mindfulness_011",
        "content": "正念应对压力：当感到压力时，暂停一下，做三次深呼吸。问自己：'此刻我的身体有什么感觉？我在想什么？我需要什么？'这个简短的暂停能打断自动化的压力反应。",
        "category": "mindfulness",
        "topic": "压力应对",
        "source": "Kabat-Zinn, J. (1990). Full Catastrophe Living",
    },
    {
        "id": "mindfulness_012",
        "content": "慈心冥想（Loving-kindness）：默念祝福语，先对自己：'愿我平安、愿我快乐、愿我健康'；再扩展到亲人、朋友、中性人、困难的人，最后到所有众生。培养善意和连接感。",
        "category": "mindfulness",
        "topic": "慈心冥想",
        "source": "Salzberg, S. (1995). Lovingkindness: The Revolutionary Art of Happiness",
    },
    {
        "id": "mindfulness_013",
        "content": "正念与反刍思维：反刍是反复回想过去的负面事件。正念练习帮助我们注意到反刍何时开始，然后温和地将注意力转回当下。不是压制想法，而是选择不继续喂养它。",
        "category": "mindfulness",
        "topic": "反刍思维",
        "source": "Segal, Z.V. et al. (2013). Mindfulness-Based Cognitive Therapy",
    },
    {
        "id": "mindfulness_014",
        "content": "日常正念锚点：选择一个日常活动作为正念提醒，如刷牙、等红灯、开门。每次做这个动作时，暂停一下，做一次有意识的深呼吸，感受当下。逐渐将正念融入生活。",
        "category": "mindfulness",
        "topic": "日常正念",
        "source": "Thich Nhat Hanh (1991). Peace Is Every Step",
    },
    {
        "id": "mindfulness_015",
        "content": "接纳与承诺：接纳不意味着喜欢或放弃改变，而是停止与现实对抗。当我们停止与痛苦情绪斗争时，反而有更多能量去做对我们真正重要的事情。",
        "category": "mindfulness",
        "topic": "接纳",
        "source": "Hayes, S.C. (2005). Get Out of Your Mind and Into Your Life",
    },

    # ═══════════════════════════════════════════════════════════
    # 睡眠卫生 — 15 条
    # ═══════════════════════════════════════════════════════════
    {
        "id": "sleep_001",
        "content": "睡眠卫生基本原则：保持规律的作息时间，即使周末也尽量在同一时间起床。规律的睡眠-觉醒节律是良好睡眠的基础，比睡眠时长更重要。",
        "category": "sleep_hygiene",
        "topic": "规律作息",
        "source": "Walker, M. (2017). Why We Sleep",
    },
    {
        "id": "sleep_002",
        "content": "睡前蓝光管理：睡前1-2小时减少手机、电脑等电子屏幕的使用。蓝光会抑制褪黑素分泌，延迟入睡时间。如必须使用，开启夜间模式或佩戴防蓝光眼镜。",
        "category": "sleep_hygiene",
        "topic": "蓝光管理",
        "source": "Harvard Health Publishing (2020). Blue Light Has a Dark Side",
    },
    {
        "id": "sleep_003",
        "content": "睡眠环境优化：卧室保持凉爽（18-22°C）、黑暗和安静。使用遮光窗帘、耳塞或白噪音机。床只用于睡眠和亲密关系，不在床上工作、看手机或看电视。",
        "category": "sleep_hygiene",
        "topic": "睡眠环境",
        "source": "National Sleep Foundation Guidelines",
    },
    {
        "id": "sleep_004",
        "content": "咖啡因与睡眠：咖啡因的半衰期约5-6小时，意味着下午2点喝的咖啡到晚上8点仍有一半在体内。建议中午12点后避免咖啡因摄入（包括茶、可乐、巧克力）。",
        "category": "sleep_hygiene",
        "topic": "咖啡因管理",
        "source": "Walker, M. (2017). Why We Sleep",
    },
    {
        "id": "sleep_005",
        "content": "睡前放松仪式：建立固定的睡前30-60分钟放松程序，如温水泡脚、轻柔拉伸、阅读纸质书、听轻音乐。这向大脑发出'准备睡觉'的信号，帮助从清醒状态过渡到睡眠。",
        "category": "sleep_hygiene",
        "topic": "睡前仪式",
        "source": "Hauri, P. & Linde, S. (1996). No More Sleepless Nights",
    },
    {
        "id": "sleep_006",
        "content": "失眠时的认知策略：如果躺在床上20分钟仍无法入睡，起床到另一个房间做些放松的事（如阅读），等有睡意再回床上。避免在床上辗转反侧，这会让大脑将床与清醒联系起来。",
        "category": "sleep_hygiene",
        "topic": "失眠应对",
        "source": "Bootzin, R.R. (1972). Stimulus Control Treatment for Insomnia",
    },
    {
        "id": "sleep_007",
        "content": "运动与睡眠：规律运动能显著改善睡眠质量，但避免在睡前3小时内进行剧烈运动。最佳运动时间是下午或傍晚，有助于体温在睡前自然下降，促进入睡。",
        "category": "sleep_hygiene",
        "topic": "运动与睡眠",
        "source": "Youngstedt, S.D. (2005). Effects of Exercise on Sleep",
    },
    {
        "id": "sleep_008",
        "content": "睡眠限制疗法：如果你在床上花8小时但只睡6小时，先将在床时间限制为6小时。当睡眠效率（实际睡眠/在床时间）达到85%以上时，每周增加15-30分钟在床时间。",
        "category": "sleep_hygiene",
        "topic": "睡眠限制",
        "source": "Spielman, A.J. et al. (1987). Treatment of Chronic Insomnia",
    },
    {
        "id": "sleep_009",
        "content": "午睡建议：如果需要午睡，控制在20-30分钟以内，且在下午3点前完成。过长或过晚的午睡会影响夜间睡眠驱动力，导致晚上难以入睡。",
        "category": "sleep_hygiene",
        "topic": "午睡管理",
        "source": "National Sleep Foundation Guidelines",
    },
    {
        "id": "sleep_010",
        "content": "睡前担忧管理：在睡前1-2小时写下明天的待办事项和当前的担忧。研究表明，将担忧'卸载'到纸上可以减少入睡前的反刍思维，缩短入睡时间。",
        "category": "sleep_hygiene",
        "topic": "睡前担忧",
        "source": "Scullin, M.K. et al. (2018). Journal of Experimental Psychology",
    },
    {
        "id": "sleep_011",
        "content": "酒精与睡眠：虽然酒精可能帮助入睡，但它会严重破坏睡眠结构，减少REM睡眠，导致后半夜频繁醒来。长期依赖酒精助眠会形成恶性循环。",
        "category": "sleep_hygiene",
        "topic": "酒精影响",
        "source": "Walker, M. (2017). Why We Sleep",
    },
    {
        "id": "sleep_012",
        "content": "光照与生物钟：早晨接受15-30分钟自然光照射有助于调节生物钟，促进夜间褪黑素正常分泌。阴天也有效，户外光照强度远高于室内照明。",
        "category": "sleep_hygiene",
        "topic": "光照调节",
        "source": "Czeisler, C.A. et al. (1999). Science",
    },
    {
        "id": "sleep_013",
        "content": "睡眠焦虑的悖论：越担心睡不着，越难入睡。接受'今晚可能睡不好也没关系'的想法，反而能降低入睡压力。一两晚睡眠不好不会对健康造成严重影响。",
        "category": "sleep_hygiene",
        "topic": "睡眠焦虑",
        "source": "Espie, C.A. (2006). Overcoming Insomnia and Sleep Problems",
    },
    {
        "id": "sleep_014",
        "content": "睡眠日记：每天记录入睡时间、醒来时间、夜间醒来次数、睡眠质量评分。持续1-2周后可以发现睡眠模式和影响因素，为改善提供数据支持。",
        "category": "sleep_hygiene",
        "topic": "睡眠记录",
        "source": "Morin, C.M. (1993). Insomnia: Psychological Assessment and Management",
    },
    {
        "id": "sleep_015",
        "content": "4-7-8呼吸法助眠：吸气4秒，屏息7秒，呼气8秒。重复3-4个循环。这种呼吸模式能激活副交感神经系统，降低心率和血压，帮助身体进入放松状态。",
        "category": "sleep_hygiene",
        "topic": "呼吸助眠",
        "source": "Weil, A. (2015). Breathing Techniques for Better Sleep",
    },

    # ═══════════════════════════════════════════════════════════
    # 社会支持理论 — 15 条
    # ═══════════════════════════════════════════════════════════
    {
        "id": "social_001",
        "content": "社会支持的四种类型：1）情感支持——倾听、共情、关心；2）信息支持——建议、指导、知识分享；3）工具性支持——实际帮助、物质援助；4）评价支持——肯定、反馈、社会比较信息。",
        "category": "social_support",
        "topic": "支持类型",
        "source": "House, J.S. (1981). Work Stress and Social Support",
    },
    {
        "id": "social_002",
        "content": "社会联系与健康：研究表明，强社会联系的人寿命更长、免疫力更强、心理健康更好。孤独感的健康风险相当于每天吸15支烟。维护社交关系是重要的健康投资。",
        "category": "social_support",
        "topic": "社交与健康",
        "source": "Holt-Lunstad, J. et al. (2010). PLoS Medicine",
    },
    {
        "id": "social_003",
        "content": "求助不是软弱：很多人认为寻求帮助是软弱的表现，但研究表明，善于求助的人心理韧性更强。求助是一种社交技能，它加深关系、建立互惠，让双方都受益。",
        "category": "social_support",
        "topic": "求助行为",
        "source": "Brown, B. (2012). Daring Greatly",
    },
    {
        "id": "social_004",
        "content": "社交能量管理：内向者在社交后需要独处时间恢复能量，这是正常的。了解自己的社交能量模式，在需要时给自己充电时间，不必为此感到内疚。",
        "category": "social_support",
        "topic": "社交能量",
        "source": "Cain, S. (2012). Quiet: The Power of Introverts",
    },
    {
        "id": "social_005",
        "content": "有效倾听的要素：全神贯注、不打断、不急于给建议、用自己的话复述对方的感受（'听起来你感到...'）、提开放式问题。有时候人们需要的不是解决方案，而是被听见。",
        "category": "social_support",
        "topic": "有效倾听",
        "source": "Rogers, C.R. (1961). On Becoming a Person",
    },
    {
        "id": "social_006",
        "content": "社交关系的质量比数量更重要：拥有2-3个可以深度交流的亲密关系，比拥有大量浅层社交更有益于心理健康。投入时间和精力维护核心关系圈。",
        "category": "social_support",
        "topic": "关系质量",
        "source": "Dunbar, R. (2010). How Many Friends Does One Person Need?",
    },
    {
        "id": "social_007",
        "content": "边界设定：健康的关系需要清晰的边界。学会说'不'不是自私，而是自我尊重。设定边界时可以温和但坚定：'我理解你的需要，但我现在无法做到这一点。'",
        "category": "social_support",
        "topic": "边界设定",
        "source": "Cloud, H. & Townsend, J. (1992). Boundaries",
    },
    {
        "id": "social_008",
        "content": "社会比较的陷阱：社交媒体放大了向上社会比较（与比自己好的人比较），导致自卑和不满。提醒自己：人们只展示生活的精彩片段，每个人都有不为人知的挣扎。",
        "category": "social_support",
        "topic": "社会比较",
        "source": "Festinger, L. (1954). A Theory of Social Comparison Processes",
    },
    {
        "id": "social_009",
        "content": "冲突解决的'我'语句：用'我感到...当...因为...'代替'你总是...'。例如：'当你迟到时我感到不被重视，因为我的时间也很宝贵'比'你总是迟到，太不尊重人了'更有建设性。",
        "category": "social_support",
        "topic": "冲突解决",
        "source": "Rosenberg, M.B. (2003). Nonviolent Communication",
    },
    {
        "id": "social_010",
        "content": "归属感需求：归属感是人类基本心理需求之一。感到被接纳、被需要、属于某个群体，对心理健康至关重要。可以通过加入兴趣小组、志愿服务或社区活动来满足这一需求。",
        "category": "social_support",
        "topic": "归属感",
        "source": "Baumeister, R.F. & Leary, M.R. (1995). Psychological Bulletin",
    },
    {
        "id": "social_011",
        "content": "感恩表达：定期向重要的人表达感谢，不仅能加强关系，还能提升双方的幸福感。可以是一条简单的消息：'谢谢你上次听我倾诉，对我帮助很大。'",
        "category": "social_support",
        "topic": "感恩表达",
        "source": "Emmons, R.A. (2007). Thanks! How the New Science of Gratitude Can Make You Happier",
    },
    {
        "id": "social_012",
        "content": "社交焦虑应对：社交焦虑的核心是害怕被负面评价。认识到：大多数人更关注自己而非评判你；即使有人不喜欢你，这也不代表你有问题——不可能让所有人都满意。",
        "category": "social_support",
        "topic": "社交焦虑",
        "source": "Clark, D.M. & Wells, A. (1995). A Cognitive Model of Social Phobia",
    },
    {
        "id": "social_013",
        "content": "互惠原则：健康的关系建立在互惠基础上。如果你总是付出而对方只是索取，这段关系可能需要重新评估。同时也检查自己是否在无意中成为只索取的一方。",
        "category": "social_support",
        "topic": "关系互惠",
        "source": "Gouldner, A.W. (1960). The Norm of Reciprocity",
    },
    {
        "id": "social_014",
        "content": "孤独感应对：感到孤独时，可以主动发起联系而非等待他人。从小步骤开始：给朋友发条消息、参加一个线上社群、或者在日常互动中多停留一会儿（如和邻居多聊几句）。",
        "category": "social_support",
        "topic": "孤独应对",
        "source": "Cacioppo, J.T. & Patrick, W. (2008). Loneliness: Human Nature and the Need for Social Connection",
    },
    {
        "id": "social_015",
        "content": "支持他人的方式：当朋友遇到困难时，先问'你需要我做什么？是想聊聊、需要建议、还是需要实际帮助？'不同的人在不同时刻需要不同类型的支持。",
        "category": "social_support",
        "topic": "支持他人",
        "source": "Burleson, B.R. (2003). Handbook of Communication and Social Interaction Skills",
    },

    # ═══════════════════════════════════════════════════════════
    # 情绪调节策略 — 20 条
    # ═══════════════════════════════════════════════════════════
    {
        "id": "emotion_001",
        "content": "情绪调节的过程模型：情绪调节可以在五个阶段介入——情境选择（避免触发情境）、情境修改（改变情境）、注意力部署（转移注意力）、认知改变（重新评价）、反应调节（调整表达）。",
        "category": "emotion_regulation",
        "topic": "情绪调节模型",
        "source": "Gross, J.J. (1998). The Emerging Field of Emotion Regulation",
    },
    {
        "id": "emotion_002",
        "content": "情绪命名效应：给情绪贴上精确的标签（如'我感到失望'而非'我心情不好'）能降低杏仁核的激活，减少情绪的强度。情绪词汇越丰富，调节能力越强。",
        "category": "emotion_regulation",
        "topic": "情绪命名",
        "source": "Lieberman, M.D. et al. (2007). Psychological Science",
    },
    {
        "id": "emotion_003",
        "content": "认知重评策略：改变对事件的解读来改变情绪反应。例如将'他没回我消息，一定是讨厌我了'重评为'他可能在忙，或者没看到消息'。这是最有效的情绪调节策略之一。",
        "category": "emotion_regulation",
        "topic": "认知重评",
        "source": "Gross, J.J. (2002). Emotion Regulation: Affective, Cognitive, and Social Consequences",
    },
    {
        "id": "emotion_004",
        "content": "情绪的波浪比喻：情绪像海浪一样，有升起、到达顶峰、然后消退的自然过程。即使是最强烈的情绪，通常也会在20-90分钟内自然减弱。学会'冲浪'而非对抗波浪。",
        "category": "emotion_regulation",
        "topic": "情绪波浪",
        "source": "Linehan, M.M. (1993). Skills Training Manual for Treating BPD",
    },
    {
        "id": "emotion_005",
        "content": "压力应对的两种策略：问题聚焦应对（解决造成压力的问题）和情绪聚焦应对（管理压力带来的情绪）。当问题可控时用前者，不可控时用后者。灵活切换是关键。",
        "category": "emotion_regulation",
        "topic": "压力应对",
        "source": "Lazarus, R.S. & Folkman, S. (1984). Stress, Appraisal, and Coping",
    },
    {
        "id": "emotion_006",
        "content": "情绪粒度：提高情绪识别的精细度。不只是'开心'或'难过'，而是区分'满足、感恩、兴奋、自豪'或'失望、内疚、嫉妒、悲伤'。精细的情绪识别有助于选择更合适的应对策略。",
        "category": "emotion_regulation",
        "topic": "情绪粒度",
        "source": "Barrett, L.F. (2017). How Emotions Are Made",
    },
    {
        "id": "emotion_007",
        "content": "TIPP技能快速调节强烈情绪：T(Temperature)用冷水洗脸降低生理唤醒；I(Intense exercise)剧烈运动消耗肾上腺素；P(Paced breathing)缓慢呼吸；P(Paired muscle relaxation)配对肌肉放松。",
        "category": "emotion_regulation",
        "topic": "TIPP技能",
        "source": "Linehan, M.M. (2015). DBT Skills Training Handouts and Worksheets",
    },
    {
        "id": "emotion_008",
        "content": "情绪日记的价值：每天花5分钟记录主要情绪、触发事件和应对方式。持续记录能帮助发现情绪模式、识别触发因素，并评估哪些应对策略最有效。",
        "category": "emotion_regulation",
        "topic": "情绪日记",
        "source": "Pennebaker, J.W. (1997). Opening Up: The Healing Power of Expressing Emotions",
    },
    {
        "id": "emotion_009",
        "content": "愤怒管理：愤怒本身不是问题，问题是破坏性的表达方式。当感到愤怒时：1）暂停——离开现场或数到10；2）识别——愤怒下面通常藏着受伤、恐惧或无力感；3）表达——冷静后用'我'语句沟通。",
        "category": "emotion_regulation",
        "topic": "愤怒管理",
        "source": "Kassinove, H. & Tafrate, R.C. (2002). Anger Management",
    },
    {
        "id": "emotion_010",
        "content": "积极情绪的扩展-建构理论：积极情绪不仅让人感觉好，还能扩展思维和行动范围，建构持久的个人资源（社交关系、技能、韧性）。有意识地培养积极情绪是一种投资。",
        "category": "emotion_regulation",
        "topic": "积极情绪",
        "source": "Fredrickson, B.L. (2001). The Role of Positive Emotions",
    },
    {
        "id": "emotion_011",
        "content": "情绪抑制的代价：长期压抑情绪不仅无效（情绪会以其他方式表现），还会增加生理压力、损害记忆力和社交关系。允许自己感受情绪，然后选择健康的表达方式。",
        "category": "emotion_regulation",
        "topic": "情绪抑制",
        "source": "Gross, J.J. & John, O.P. (2003). Journal of Personality and Social Psychology",
    },
    {
        "id": "emotion_012",
        "content": "心流体验：当技能水平与挑战难度匹配时，人会进入完全投入的'心流'状态。寻找能让你忘记时间的活动，定期进入心流状态有助于提升整体幸福感和生活满意度。",
        "category": "emotion_regulation",
        "topic": "心流体验",
        "source": "Csikszentmihalyi, M. (1990). Flow: The Psychology of Optimal Experience",
    },
    {
        "id": "emotion_013",
        "content": "悲伤的正常化：悲伤是对失去的自然反应，不需要'修复'。悲伤没有固定的时间表，每个人的节奏不同。允许自己悲伤，同时在准备好时逐渐重建生活的意义。",
        "category": "emotion_regulation",
        "topic": "悲伤处理",
        "source": "Worden, J.W. (2009). Grief Counseling and Grief Therapy",
    },
    {
        "id": "emotion_014",
        "content": "感恩练习：每天写下3件感恩的事，无论多小（一杯好喝的咖啡、朋友的一条消息、完成了一项任务）。持续练习能重新训练大脑关注积极面，提升整体幸福感。",
        "category": "emotion_regulation",
        "topic": "感恩练习",
        "source": "Emmons, R.A. & McCullough, M.E. (2003). Journal of Personality and Social Psychology",
    },
    {
        "id": "emotion_015",
        "content": "情绪韧性：韧性不是不感到痛苦，而是在困难后能恢复和成长的能力。培养韧性的要素：社会连接、乐观但现实的态度、自我效能感、找到意义和目的。",
        "category": "emotion_regulation",
        "topic": "情绪韧性",
        "source": "Southwick, S.M. & Charney, D.S. (2012). Resilience: The Science of Mastering Life's Greatest Challenges",
    },
    {
        "id": "emotion_016",
        "content": "自我关怀休息：当情绪耗竭时，给自己许可去休息。这不是懒惰，而是必要的恢复。就像手机需要充电一样，人也需要定期补充情绪能量。",
        "category": "emotion_regulation",
        "topic": "自我关怀",
        "source": "Neff, K. (2011). Self-Compassion: The Proven Power of Being Kind to Yourself",
    },
    {
        "id": "emotion_017",
        "content": "情绪传染：情绪具有传染性，我们会不自觉地'感染'周围人的情绪。注意你经常接触的人和内容（包括社交媒体）对你情绪的影响，有意识地选择积极的情绪环境。",
        "category": "emotion_regulation",
        "topic": "情绪传染",
        "source": "Hatfield, E. et al. (1993). Emotional Contagion",
    },
    {
        "id": "emotion_018",
        "content": "写作疗愈：连续4天每天写15-20分钟关于深层情感体验的文字，不必在意语法或结构。研究表明这能改善免疫功能、减少就医次数、提升心理健康。",
        "category": "emotion_regulation",
        "topic": "表达性写作",
        "source": "Pennebaker, J.W. (1997). Opening Up: The Healing Power of Expressing Emotions",
    },
    {
        "id": "emotion_019",
        "content": "情绪与身体的连接：情绪会在身体中产生物理感觉——焦虑可能表现为胸闷、胃部不适；悲伤可能感觉身体沉重。关注身体信号有助于更早识别和应对情绪变化。",
        "category": "emotion_regulation",
        "topic": "身心连接",
        "source": "Van der Kolk, B. (2014). The Body Keeps the Score",
    },
    {
        "id": "emotion_020",
        "content": "意义建构：在困难经历中寻找意义或成长点，能帮助情绪恢复。这不是说困难是'好事'，而是问'我从中学到了什么？''这如何让我变得更强？'创伤后成长是真实存在的。",
        "category": "emotion_regulation",
        "topic": "意义建构",
        "source": "Tedeschi, R.G. & Calhoun, L.G. (2004). Posttraumatic Growth",
    },
]


# ╔══════════════════════════════════════════════════════════════╗
# ║  初始化逻辑                                                   ║
# ╚══════════════════════════════════════════════════════════════╝

COLLECTION_NAME = "domain_knowledge_psychology"


def init_domain_knowledge(force: bool = False) -> int:
    """
    初始化领域知识库，将精选条目写入 Chroma 集合。

    :param force: 如果为 True，即使集合已存在也重新写入
    :return: 写入的条目数
    """
    from app.services.vector_service import _get_chroma_client, _embedding_fn

    client = _get_chroma_client()

    # 检查集合是否已存在
    existing_collections = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing_collections and not force:
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=_embedding_fn,
        )
        count = collection.count()
        if count > 0:
            logger.info(
                "集合 '%s' 已存在且包含 %d 条数据。使用 --force 参数强制重新初始化。",
                COLLECTION_NAME,
                count,
            )
            return count

    # 创建或获取集合
    if force and COLLECTION_NAME in existing_collections:
        client.delete_collection(COLLECTION_NAME)
        logger.info("已删除旧集合 '%s'", COLLECTION_NAME)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn,
        metadata={"description": "心理学领域知识库 — 共享只读集合"},
    )

    # 批量写入
    batch_size = 20
    total = len(DOMAIN_KNOWLEDGE_ENTRIES)
    written = 0

    for i in range(0, total, batch_size):
        batch = DOMAIN_KNOWLEDGE_ENTRIES[i:i + batch_size]

        ids = [entry["id"] for entry in batch]
        documents = [entry["content"] for entry in batch]
        metadatas = [
            {
                "category": entry["category"],
                "topic": entry["topic"],
                "source": entry["source"],
            }
            for entry in batch
        ]

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        written += len(batch)
        logger.info("写入进度: %d/%d 条", written, total)

    logger.info(
        "领域知识库初始化完成！集合 '%s' 共 %d 条条目。",
        COLLECTION_NAME,
        collection.count(),
    )
    logger.info("覆盖领域: CBT(%d), 正念(%d), 睡眠卫生(%d), 社会支持(%d), 情绪调节(%d)",
        sum(1 for e in DOMAIN_KNOWLEDGE_ENTRIES if e["category"] == "cbt"),
        sum(1 for e in DOMAIN_KNOWLEDGE_ENTRIES if e["category"] == "mindfulness"),
        sum(1 for e in DOMAIN_KNOWLEDGE_ENTRIES if e["category"] == "sleep_hygiene"),
        sum(1 for e in DOMAIN_KNOWLEDGE_ENTRIES if e["category"] == "social_support"),
        sum(1 for e in DOMAIN_KNOWLEDGE_ENTRIES if e["category"] == "emotion_regulation"),
    )

    return collection.count()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="初始化心理学领域知识库")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新初始化（删除已有数据后重新写入）",
    )
    args = parser.parse_args()

    count = init_domain_knowledge(force=args.force)
    print(f"\n✅ 领域知识库初始化完成，共 {count} 条条目。")
