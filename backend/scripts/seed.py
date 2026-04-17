"""Seed Terra Rex Energy demo data: admin user, agent profile, KB, FAQs."""
from __future__ import annotations

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.agent import AgentProfile, AgentProfileKbLink
from app.models.knowledge import FaqEntry, KnowledgeBase, KnowledgeDocument
from app.models.user import Role, User


DOCS = [
    {
        "title": "Terra Rex Energy — company overview",
        "category": "company_overview",
        "content": """Terra Rex Energy is a full-service solar EPC based in India, offering turnkey
rooftop and ground-mounted solar solutions for residential, commercial, and
industrial customers. We handle site survey, design, installation,
government subsidy application, net-metering, and ongoing maintenance.""",
    },
    {
        "title": "Residential solar — what we offer",
        "category": "residential_solar",
        "content": """Residential solar systems from Terra Rex come in sizes from 1 kWp to 10 kWp.
Typical 3 kWp system powers a mid-size home with 4-6 fans, 10-12 LEDs, a
fridge, TV, and a washing machine. Payback period is usually 4-6 years
depending on consumption and subsidy. We install Tier-1 mono-PERC panels and
on-grid inverters with 5-year product warranty and 25-year performance
warranty.""",
    },
    {
        "title": "Commercial & industrial solar",
        "category": "commercial_solar",
        "content": """For factories, warehouses, and offices, Terra Rex designs solar solutions
between 10 kWp and 1 MWp. Customers typically save 30-50% on monthly bills.
We offer both CAPEX and OPEX (zero upfront cost) models. Depreciation benefit
up to 40% in the first year is available under accelerated depreciation.""",
    },
    {
        "title": "Installation process — step by step",
        "category": "installation_process",
        "content": """1. Free site survey and shadow analysis.
2. Detailed proposal with design, savings estimate, and subsidy eligibility.
3. Agreement and advance payment (20%).
4. Procurement — panels, inverter, structure, cabling.
5. Installation — 2 to 5 days depending on system size.
6. Net-metering application filed with the discom.
7. Commissioning and handover with a mobile monitoring app.""",
    },
    {
        "title": "Subsidy & PM Surya Ghar",
        "category": "subsidy",
        "content": """Under the PM Surya Ghar: Muft Bijli Yojana, residential systems up to 3 kWp
get a central subsidy of Rs 30,000 per kW, capped at Rs 78,000 for 3 kWp and
above. Eligibility depends on the discom approval and panel/inverter being on
the ALMM list. Terra Rex files the subsidy application on your behalf.""",
    },
    {
        "title": "EMI / financing options",
        "category": "financing",
        "content": """We partner with Bajaj Finserv, HDFC Home Loans, and local PSU banks to offer
EMI options from 12 to 60 months. No-cost EMI is available on certain
system sizes and cards. Typical EMI for a 3 kWp system starts around Rs
3,500/month (subject to subsidy and bank approval).""",
    },
    {
        "title": "Maintenance & AMC",
        "category": "maintenance",
        "content": """Monthly cleaning and an annual inspection are recommended. Terra Rex offers
two AMC plans: BASIC (quarterly cleaning + annual inspection) and PREMIUM
(monthly cleaning + sensor monitoring + 24h response). Every new system
includes a 12-month free comprehensive maintenance.""",
    },
    {
        "title": "Warranty details",
        "category": "warranty",
        "content": """Panels: 12-year product warranty, 25-year linear performance warranty.
Inverter: 5-year product warranty, extendable up to 10 years.
Mounting structure: 10-year anti-corrosion warranty.
Workmanship: 2-year on-site.""",
    },
    {
        "title": "Callback & site survey prep",
        "category": "callback_prep",
        "content": """Before a site visit please keep the last 3 months' electricity bills handy
and a photograph of the roof (or open terrace) ready. For commercial sites
please confirm sanctioned load and feeder availability.""",
    },
    {
        "title": "Objection handling — common concerns",
        "category": "objection_handling",
        "content": """- 'Panels break in storm': Tier-1 panels are tested for wind up to 240 km/h
and hail impact; our structures are cyclone-rated.
- 'Roof leakage risk': we use ballasted or engineered footings; no roof
penetration on RCC is our standard.
- 'Cloudy day performance': modern mono-PERC panels produce 15-25% of rated
output on cloudy days; net-metering covers the gap.""",
    },
]


FAQS = [
    ("How much does a 3 kW solar system cost in India?",
     "A 3 kW rooftop system typically costs Rs 1.8–2.1 lakh before subsidy. With the PM Surya Ghar subsidy of up to Rs 78,000, your effective cost drops to around Rs 1–1.3 lakh.",
     "financing"),
    ("Is there a government subsidy for solar?",
     "Yes. Under PM Surya Ghar, residential installations up to 3 kW get Rs 30,000 per kW (max Rs 78,000). Terra Rex files the subsidy application for you.",
     "subsidy"),
    ("How long does installation take?",
     "A residential 3 kW system is installed in 2–3 days. Net-metering approval from your discom can take 2–4 weeks.",
     "installation_process"),
    ("What is the warranty?",
     "Panels carry a 25-year performance warranty, inverter 5 years (extendable), and structure 10 years.",
     "warranty"),
    ("Can I book a free site visit?",
     "Yes — share your city and a convenient time, and our specialist will reach out to schedule.",
     "callback_prep"),
]


AGENT = {
    "name": "Terra Rex Sales & Support Agent",
    "purpose": "Handle solar sales enquiries, lead qualification, and basic service support for Terra Rex Energy customers on WhatsApp.",
    "tone": "warm, consultative, trustworthy — like a helpful solar advisor, not a pushy salesperson",
    "response_style": "concise, 2–4 short lines, one clarifying question when needed",
    "languages_supported": ["en", "hi"],
    "greeting_style": "Hi! I'm the Terra Rex Energy assistant. How can I help with your solar plans today?",
    "escalation_keywords": ["human", "agent", "call me", "speak to someone", "representative"],
    "forbidden_claims": [
        "guaranteed return on investment figures",
        "promises of a specific subsidy amount before eligibility check",
        "any legal or tax advice",
    ],
    "allowed_domains": ["solar", "rooftop", "energy", "subsidy", "EMI", "site visit", "AMC", "warranty"],
    "fallback_message": "Let me connect you with a Terra Rex specialist who can help with this specifically.",
    "human_handoff_message": "I'll have a Terra Rex solar advisor reach out to you shortly. Can I confirm your city and the best time to call?",
    "business_hours_behavior": "respond_always",
    "instructions": """When a customer asks about pricing, first ask for their city and approximate monthly electricity bill to give a realistic estimate range — never quote a single number without context. When someone mentions subsidy, remind them eligibility depends on discom approval and ALMM-listed components. If a customer sounds dissatisfied about an existing installation, acknowledge, and offer a callback from the service team.""",
    "is_default": True,
}


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == "admin@terrarex.in")) is None:
            admin = User(
                email="admin@terrarex.in",
                name="Terra Rex Admin",
                password_hash=hash_password("admin123"),
                role=Role.admin,
            )
            db.add(admin)
            print("created admin user: admin@terrarex.in / admin123")

        if db.scalar(select(User).where(User.email == "ops@terrarex.in")) is None:
            db.add(User(
                email="ops@terrarex.in",
                name="Ops Manager",
                password_hash=hash_password("ops12345"),
                role=Role.campaign_manager,
            ))
            db.add(User(
                email="support@terrarex.in",
                name="Support Agent",
                password_hash=hash_password("support12345"),
                role=Role.support_agent,
            ))

        kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.name == "Terra Rex Core KB"))
        if kb is None:
            kb = KnowledgeBase(
                name="Terra Rex Core KB",
                description="Primary KB: products, subsidy, installation, warranty, AMC, objections.",
            )
            db.add(kb)
            db.flush()
            for d in DOCS:
                db.add(KnowledgeDocument(
                    kb_id=kb.id,
                    title=d["title"],
                    category=d["category"],
                    content=d["content"],
                    source_kind="text",
                ))
            for q, a, cat in FAQS:
                db.add(FaqEntry(kb_id=kb.id, question=q, answer=a, category=cat))
            print(f"created KB with {len(DOCS)} docs and {len(FAQS)} FAQs")

        agent = db.scalar(select(AgentProfile).where(AgentProfile.name == AGENT["name"]))
        if agent is None:
            agent = AgentProfile(**AGENT)
            db.add(agent)
            db.flush()
            db.add(AgentProfileKbLink(agent_profile_id=agent.id, kb_id=kb.id))
            print("created default agent profile and attached Terra Rex KB")

        db.commit()
        print("seed complete")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
