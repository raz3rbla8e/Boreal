# ── AUTO-CATEGORIZATION RULES ────────────────────────────────────────────────
# Keyword → category mapping used at import time.

CATEGORY_RULES = {
    "Subscriptions": [
        "claude.ai", "anthropic", "netflix", "spotify", "apple.com/bill", "google one",
        "microsoft 365", "adobe", "notion", "chatgpt", "openai", "dropbox", "icloud",
        "youtube premium", "duolingo", "amazon prime", "prime video",
        "crunchyroll", "paramount+", "canva", "github", "hbo max", "nord vpn",
        "expressvpn", "audible", "kindle unlimited", "apple tv",
    ],
    "Fuel": [
        "shell", "esso", "petro-canada", "petro canada", "ultramar", "pioneer", "irving",
        "suncor", "husky", "pronto", "gas station", "circle k", "couche tard",
        "shefield", "sheffield", "7-eleven fuel", "costco gas", "mobil ",
        "on the run", "super save gas", "co-op gas", "canadian tire gas",
    ],
    "Groceries": [
        "loblaws", "no frills", "sobeys", "metro", "food basics", "freshco", "farm boy",
        "whole foods", "costco wholesale", "superstore", "real canadian", "t&t", "maxi",
        "provigo", "iga", "safeway", "save on food", "independent", "freshmart",
        "grocery", "supermarche", "epicerie", "wmt suprctr", "wal-mart", "walmart",
        "voila", "instacart", "pc express", "flashfood",
    ],
    "Pharmacy": [
        "shoppers drug", "rexall", "pharmasave", "jean coutu", "uniprix", "proxim",
        "guardian", "london drugs", "pharmacy", "drug mart", "supplement", "vitamin",
    ],
    "Healthcare": [
        "physio", "dentist", "dental", "doctor", "clinic", "optometrist", "medical",
        "hospital", "diagnosis", "diagnostics", "planet fitness", "goodlife",
        "anytime fitness", "gym", "yoga", "pilates", "abc*planet", "massage", "therapy",
        "lifelab", "chiropract", "walk-in", "dermatol",
    ],
    "Phone": [
        "fido", "koodo", "public mobile", "lucky mobile", "virgin mobile",
        "bell mobility", "telus mobile", "rogers mobile", "rogers wireless",
        "freedom mobile", "chatr", "phone bill",
    ],
    "Internet": [
        "bell internet", "rogers internet", "videotron", "shaw", "eastlink", "cogeco",
        "teksavvy", "distributel", "start.ca", "vmedia",
    ],
    "Utilities": [
        "hydro ottawa", "hydro one", "bc hydro", "enbridge", "union gas",
        "atco gas", "fortis", "water bill", "toronto hydro", "alectra",
        "nova scotia power", "manitoba hydro", "saskpower", "epcor",
    ],
    "Clothing": [
        "winners", "marshalls", "sport chek", "atmosphere", "nike", "adidas",
        "h&m", "zara", "uniqlo", "old navy", "aritzia", "lululemon",
        "simons", "the bay", "hudson's bay", "nordstrom", "reitmans", "ssense", "roots",
        "gap #", "gap factory", "mark's", "marks work",
    ],
    "Home": [
        "ikea", "canadian tire", "home depot", "rona", "home hardware",
        "wayfair", "structube", "article", "restoration hardware", "pottery barn",
        "kitchen stuff", "bed bath", "linen chest",
    ],
    "Insurance": [
        "insurance", "intact", "aviva", "state farm", "belairdirect", "wawanesa",
        "td insurance", "rbc insurance", "allstate", "cooperators", "desjardins insur",
    ],
    "Travel": [
        "airbnb", "hotel", "expedia", "booking.com", "air canada", "westjet", "porter",
        "swoop", "flair", "vrbo", "marriott", "hilton", "delta hotel", "best western",
        "kayak", "hostel", "motel", "resort", "via rail", "sunwing",
    ],
    "Education": [
        "carleton", "university", "college", "textbook", "udemy", "coursera",
        "linkedin learn", "skillshare", "pluralsight", "tuition", "osap", "bookstore",
        "mcgill", "uoft", "ubc", "western university", "queens university",
    ],
    "Entertainment": [
        "steam", "epic games", "xbox", "playstation", "nintendo", "cineplex", "landmark",
        "google play", "disney+", "twitch", "riot games", "crave", "tidal", "deezer",
        "gaming", "movie", "theatre", "concert", "ticketmaster", "eventbrite",
        "billetterie", "lcbo", "rao #", "liquor store", "beer store", "saq",
        "lotto", "lottery",
    ],
    "Transport": [
        "uber", "lyft", "oc transpo", "ttc", "stm", "translink", "presto", "parking",
        "taxi", "transit", "impark", "indigo park", "greyhound", "flixbus", "train",
        "enterprise rent", "budget rent", "hertz", "avis", "zipcar",
        "communauto", "turo", "go transit",
    ],
    "Eating Out": [
        "mcdonald", "tim horton", "subway", "starbucks", "uber eat", "skip the dishes",
        "doordash", "pizza", "burger", "wendy", "kfc", "taco bell", "harvey's", "a&w",
        "mary brown", "popeye", "chipotle", "freshii", "pita pit", "swiss chalet",
        "boston pizza", "jack astor", "milestones", "cactus club", "earls", "montana",
        "st-hubert", "five guys", "nandos", "pho ", "sushi", "thai", "domino",
        "papa john", "little caesar", "pizza pizza", "pizza hut", "hero burger",
        "mucho burrito", "shawarma", "falafel", "osmow", "6ixty wing", "happy lamb",
        "burrito", "chick-fil", "dairy queen", "d spot", "vietnamese", "restaurant",
        "cafe", "coffee", "bakery", "diner", "grill", "bistro",
        "eatery", "food court", "hot pot", "wings", "ramen", "poke", "bubble tea",
        "moxie", "denny", "ihop", "east side mario", "the keg", "joey", "menchie",
        "booster juice", "second cup", "new york fries", "panago", "extreme pita",
        "wild wing", "st louis", "scores", "baton rouge", "mr sub", "country style",
        "la belle province", "cora breakfast", "fatburger", "smokes poutine",
    ],
    "Shopping": [
        "amazon", "target", "ebay", "etsy", "aliexpress", "shein", "best buy",
        "staples", "the source", "indigo", "chapters", "paypal", "shopify",
        "dollarama", "dollar tree", "giant tiger", "tanger outlet", "rfbt",
        "homesense", "apple store", "samsung", "microsoft store", "dell",
        "value village", "goodwill", "sport check",
    ],
    "Misc": [
        "detail my ride", "car wash", "car detail", "auto detail", "dry clean",
        "laundromat", "post office", "fedex", "ups", "purolator", "canada post",
        "storage", "moving",
    ],
}

# Priority order for category matching
_PRIORITY_ORDER = [
    "Subscriptions", "Fuel", "Groceries", "Pharmacy", "Healthcare",
    "Phone", "Internet", "Utilities", "Clothing", "Home", "Insurance",
    "Travel", "Education", "Entertainment", "Transport", "Eating Out",
    "Shopping", "Misc",
]


def categorize(name: str, learned: dict = None) -> str:
    n = name.lower().strip()
    # Hard overrides — check multi-word matches before single-word rules
    if "costco gas" in n:
        return "Fuel"
    if "uber eat" in n or "ubereats" in n:
        return "Eating Out"
    # User-learned merchants (highest priority)
    if learned:
        for keyword, cat in learned.items():
            if keyword in n:
                return cat
    # Rule-based (check specific categories before generic ones)
    for cat in _PRIORITY_ORDER:
        for kw in CATEGORY_RULES.get(cat, []):
            if kw in n:
                return cat
    return "UNCATEGORIZED"


def load_learned_dict(db) -> dict:
    rows = db.execute("SELECT keyword, category FROM learned_merchants").fetchall()
    return {r["keyword"]: r["category"] for r in rows}
