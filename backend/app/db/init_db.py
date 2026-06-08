"""数据库初始化脚本"""

from app.db.session import init_db, SessionLocal
from app.models import CustomRule


def seed_default_rules():
    """导入默认审核规则"""
    default_rules = [
        {
            "name": "风险条款检查",
            "prompt_template": (
                "请检查以下合同条款是否存在法律风险，包括但不限于："
                "责任不对等、赔偿上限过低、管辖权不明确。"
                "给出风险等级(high/medium/low)和具体建议。"
            ),
            "category": "system",
            "is_active": True,
        },
        {
            "name": "模糊用语检查",
            "prompt_template": (
                "请检查以下合同条款是否包含模糊、歧义用语"
                "（如“合理”、“及时”、“必要”等），"
                "指出模糊之处并建议具体化。"
            ),
            "category": "system",
            "is_active": True,
        },
        {
            "name": "合规性检查",
            "prompt_template": (
                "请检查以下合同条款是否符合中国《民法典》合同编的基本要求，"
                "指出可能不合规的内容。"
            ),
            "category": "system",
            "is_active": True,
        },
        {
            "name": "完整性检查",
            "prompt_template": (
                "请检查以下合同是否缺少常见必要条款"
                "（如违约责任、争议解决、保密条款、知识产权归属等），"
                "列出缺失项。"
            ),
            "category": "system",
            "is_active": True,
        },
    ]

    db = SessionLocal()
    try:
        for rule_data in default_rules:
            existing = db.query(CustomRule).filter(
                CustomRule.name == rule_data["name"],
                CustomRule.category == "system",
            ).first()
            if not existing:
                rule = CustomRule(**rule_data)
                db.add(rule)
        db.commit()
        print("默认规则已导入。")
    finally:
        db.close()


if __name__ == "__main__":
    print("初始化数据库表...")
    init_db()
    print("导入默认审核规则...")
    seed_default_rules()
    print("数据库初始化完成。")
