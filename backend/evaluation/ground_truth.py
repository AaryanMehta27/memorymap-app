"""
Ground truth dataset for MemoryMap RAG evaluation.

Each entry represents a patient query and the expected correct retrieval result.
This simulates the tags that would exist in Supabase after caregivers photograph
and tag rooms in a home.
"""


# Simulated tag database — what Supabase would return for a home
MOCK_HOME_TAGS = [
    {
        "id": "tag-001",
        "label": "medicine cabinet",
        "room_name": "Bathroom",
        "position": "upper-left wall above sink",
        "notes": "White cabinet with a red cross symbol, mounted above the sink",
        "photo_url": "https://storage.example.com/bathroom-01.jpg",
    },
    {
        "id": "tag-002",
        "label": "bedside drawer",
        "room_name": "Master Bedroom",
        "position": "right side of the bed",
        "notes": "Small wooden nightstand with two drawers",
        "photo_url": "https://storage.example.com/bedroom-01.jpg",
    },
    {
        "id": "tag-003",
        "label": "kitchen pantry",
        "room_name": "Kitchen",
        "position": "far-right corner near fridge",
        "notes": "Tall white pantry cabinet with pull-out shelves",
        "photo_url": "https://storage.example.com/kitchen-01.jpg",
    },
    {
        "id": "tag-004",
        "label": "shoe rack",
        "room_name": "Entryway",
        "position": "left wall near front door",
        "notes": "Three-tier wooden shoe rack with about 8 pairs visible",
        "photo_url": "https://storage.example.com/entryway-01.jpg",
    },
    {
        "id": "tag-005",
        "label": "bookshelf",
        "room_name": "Living Room",
        "position": "back wall, center",
        "notes": "Large 5-shelf bookcase, dark brown wood, also has photo frames",
        "photo_url": "https://storage.example.com/living-01.jpg",
    },
    {
        "id": "tag-006",
        "label": "key hook board",
        "room_name": "Entryway",
        "position": "right wall at eye level",
        "notes": "Wooden board with 4 metal hooks, currently has 2 sets of keys",
        "photo_url": "https://storage.example.com/entryway-02.jpg",
    },
    {
        "id": "tag-007",
        "label": "refrigerator",
        "room_name": "Kitchen",
        "position": "left wall",
        "notes": "Large stainless steel double-door fridge with water dispenser",
        "photo_url": "https://storage.example.com/kitchen-02.jpg",
    },
    {
        "id": "tag-008",
        "label": "coat closet",
        "room_name": "Entryway",
        "position": "right side, near staircase",
        "notes": "White sliding door closet, coats and umbrellas inside",
        "photo_url": "https://storage.example.com/entryway-03.jpg",
    },
    {
        "id": "tag-009",
        "label": "bathroom cabinet under sink",
        "room_name": "Bathroom",
        "position": "below the sink",
        "notes": "Cabinet with cleaning supplies and extra toiletries",
        "photo_url": "https://storage.example.com/bathroom-02.jpg",
    },
    {
        "id": "tag-010",
        "label": "desk drawer",
        "room_name": "Home Office",
        "position": "under the desk, right side",
        "notes": "Rolling drawer unit with 3 drawers, top one has pens and sticky notes",
        "photo_url": "https://storage.example.com/office-01.jpg",
    },
    {
        "id": "tag-011",
        "label": "microwave",
        "room_name": "Kitchen",
        "position": "countertop, left of the stove",
        "notes": "Black microwave on the counter",
        "photo_url": "https://storage.example.com/kitchen-03.jpg",
    },
    {
        "id": "tag-012",
        "label": "laundry basket",
        "room_name": "Master Bedroom",
        "position": "corner near the closet door",
        "notes": "Woven wicker basket for dirty clothes",
        "photo_url": "https://storage.example.com/bedroom-02.jpg",
    },
    {
        "id": "tag-013",
        "label": "TV stand",
        "room_name": "Living Room",
        "position": "front wall, facing couch",
        "notes": "Low wooden TV stand with two shelves underneath — has remotes and game console",
        "photo_url": "https://storage.example.com/living-02.jpg",
    },
    {
        "id": "tag-014",
        "label": "spice rack",
        "room_name": "Kitchen",
        "position": "wall-mounted, above the stove",
        "notes": "Small wooden rack with about 12 labeled spice jars",
        "photo_url": "https://storage.example.com/kitchen-04.jpg",
    },
    {
        "id": "tag-015",
        "label": "wardrobe",
        "room_name": "Master Bedroom",
        "position": "left wall",
        "notes": "Large white wardrobe with mirror doors",
        "photo_url": "https://storage.example.com/bedroom-03.jpg",
    },
]


# Ground truth query-answer pairs: question -> list of relevant tag IDs
# Each query should ideally retrieve these specific tags
GROUND_TRUTH_QUERIES = [
    {
        "query": "Where are my blood pressure pills?",
        "relevant_tag_ids": ["tag-001", "tag-002", "tag-009"],
        "best_tag_id": "tag-001",  # medicine cabinet is the most relevant
        "category": "medication",
    },
    {
        "query": "Where did I put my keys?",
        "relevant_tag_ids": ["tag-006"],
        "best_tag_id": "tag-006",
        "category": "everyday_item",
    },
    {
        "query": "Where is my winter coat?",
        "relevant_tag_ids": ["tag-008", "tag-015"],
        "best_tag_id": "tag-008",
        "category": "clothing",
    },
    {
        "query": "I need to find the TV remote.",
        "relevant_tag_ids": ["tag-013"],
        "best_tag_id": "tag-013",
        "category": "everyday_item",
    },
    {
        "query": "Where can I find cinnamon?",
        "relevant_tag_ids": ["tag-014", "tag-003"],
        "best_tag_id": "tag-014",
        "category": "food_item",
    },
    {
        "query": "Where are my shoes?",
        "relevant_tag_ids": ["tag-004"],
        "best_tag_id": "tag-004",
        "category": "clothing",
    },
    {
        "query": "I want to heat up some leftovers.",
        "relevant_tag_ids": ["tag-011", "tag-007"],
        "best_tag_id": "tag-011",
        "category": "appliance",
    },
    {
        "query": "Where is my pen?",
        "relevant_tag_ids": ["tag-010"],
        "best_tag_id": "tag-010",
        "category": "everyday_item",
    },
    {
        "query": "I need to find a book I was reading.",
        "relevant_tag_ids": ["tag-005", "tag-002"],
        "best_tag_id": "tag-005",
        "category": "everyday_item",
    },
    {
        "query": "Where should I put my dirty clothes?",
        "relevant_tag_ids": ["tag-012"],
        "best_tag_id": "tag-012",
        "category": "everyday_item",
    },
    {
        "query": "Where is the milk?",
        "relevant_tag_ids": ["tag-007"],
        "best_tag_id": "tag-007",
        "category": "food_item",
    },
    {
        "query": "I need my toothbrush.",
        "relevant_tag_ids": ["tag-001", "tag-009"],
        "best_tag_id": "tag-009",
        "category": "hygiene",
    },
    {
        "query": "Where is the umbrella?",
        "relevant_tag_ids": ["tag-008"],
        "best_tag_id": "tag-008",
        "category": "everyday_item",
    },
    {
        "query": "Where did I keep the photo albums?",
        "relevant_tag_ids": ["tag-005"],
        "best_tag_id": "tag-005",
        "category": "sentimental",
    },
    {
        "query": "I need to take my morning vitamins.",
        "relevant_tag_ids": ["tag-001", "tag-002", "tag-009"],
        "best_tag_id": "tag-001",
        "category": "medication",
    },
    {
        "query": "Where is my laptop charger?",
        "relevant_tag_ids": ["tag-010"],
        "best_tag_id": "tag-010",
        "category": "electronics",
    },
    {
        "query": "I can't find my jacket.",
        "relevant_tag_ids": ["tag-008", "tag-015"],
        "best_tag_id": "tag-008",
        "category": "clothing",
    },
    {
        "query": "Where do we keep the pasta?",
        "relevant_tag_ids": ["tag-003"],
        "best_tag_id": "tag-003",
        "category": "food_item",
    },
    {
        "query": "I need sticky notes for a reminder.",
        "relevant_tag_ids": ["tag-010"],
        "best_tag_id": "tag-010",
        "category": "office_supply",
    },
    {
        "query": "Where is my game controller?",
        "relevant_tag_ids": ["tag-013"],
        "best_tag_id": "tag-013",
        "category": "electronics",
    },
]
