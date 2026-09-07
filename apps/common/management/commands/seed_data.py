"""
Management command to seed the database with realistic initial data for development.

This command populates the database with:
- Foundational data (UOMs, Branches)
- User accounts with assigned roles (Admin, Purchaser, etc.)
- Product Categories -> Products (Full set from Excel)
- Inventory Categories -> Subcategories -> Inventory Items (Full set from Demand Sheets)

Usage:
    python manage.py seed_data
"""

import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.branch.models import Branch
from apps.inventory.models import (
    InventoryCategory,
    InventoryItem,
    UnitOfMeasure,
)
from apps.products.models import Product, ProductCategory

User = get_user_model()


class Command(BaseCommand):
    help = "Seed the database with core entities (Users, Branches, Products, Inventory)"

    def handle(self, *_args, **_options):
        self.stdout.write("Starting comprehensive seed data generation...")

        self.stdout.write("  - Running create_default_groups...")
        call_command("create_default_groups")

        self.stdout.write("  - Creating foundational data (UOMs, Branches)...")
        uoms = self.create_uoms()
        branches = self.create_branches()

        self.stdout.write("  - Creating users and assigning groups...")
        self.create_users(branches)

        self.stdout.write(
            "  - Creating hierarchical inventory items and branch stocks..."
        )
        self.create_inventory(uoms)

        self.stdout.write(
            "  - Creating product categories and products (including branch menus)..."
        )
        self.create_products(branches)

        self.stdout.write(
            self.style.SUCCESS("Seed data generation completed successfully!")
        )

    def create_uoms(self):
        data = [
            ("Kilogram", "kg"),
            ("Gram", "g"),
            ("Piece", "pcs"),
            ("Litre", "L"),
            ("Box", "box"),
            ("Packet", "pkt"),
        ]
        uoms = []
        for name, abbr in data:
            uom, _ = UnitOfMeasure.objects.get_or_create(
                abbreviation=abbr, defaults={"name": name}
            )
            uoms.append(uom)
        return uoms

    def create_branches(self):
        data = [
            ("BR001", "Raya", "Raya Commercial", "+923000000001"),
        ]
        branches = []
        for code, name, addr, phone in data:
            branch, _ = Branch.objects.get_or_create(
                branch_code=code,
                defaults={"name": name, "address": addr, "phone": phone},
            )
            branches.append(branch)
        return branches

    def create_users(self, branches):
        # Global Admin
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        admin_user, admin_created = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@example.com",
                "is_staff": True,
                "phone": "+923000000000",
            },
        )
        if admin_created:
            admin_user.set_password("admin.123")
            admin_user.save()
        admin_user.groups.add(admin_group)

        bm_group, _ = Group.objects.get_or_create(name="Branch Manager")
        purchaser_group, _ = Group.objects.get_or_create(name="Purchaser")

        raya_branch = next((b for b in branches if "Raya" in b.name), None)
        if raya_branch:
            # Branch Manager
            bm_user, bm_created = User.objects.get_or_create(
                username="bm",
                defaults={
                    "email": "bm@example.com",
                    "is_staff": True,
                    "phone": "+923000000010",
                    "branch": raya_branch,
                },
            )
            if bm_created:
                bm_user.set_password("user.123")
                bm_user.save()
            bm_user.groups.add(bm_group)

            # Purchaser
            purchaser_user, p_created = User.objects.get_or_create(
                username="purchaser",
                defaults={
                    "email": "purchaser@example.com",
                    "is_staff": True,
                    "phone": "+923000000011",
                    "branch": raya_branch,
                },
            )
            if p_created:
                purchaser_user.set_password("user.123")
                purchaser_user.save()
            purchaser_user.groups.add(purchaser_group)

    def create_inventory(self, uoms):
        # Full extracted inventory hierarchy
        inventory_hierarchy = [
            {
                "category": "Continental Section",
                "subcategories": [
                    {
                        "name": "MEATS",
                        "items": [
                            "Austrailian Lamb Chop",
                            "Beef Mince",
                            "Beef Ribeye Cab Chilled",
                            "Beef Undercut",
                            "Chicken Breast K&N's",
                            "Chicken Wings K&N's",
                            "Jumbo Prawn",
                            "Lobster",
                            "Prawns 11/15",
                            "Salmon Fillet Skin On",
                            "Sole Fish",
                            "Turkey Break fast Slice",
                        ],
                    },
                    {
                        "name": "VEGETABLES",
                        "items": [
                            "Asparagus 500gm",
                            "Avacado",
                            "Beet Root",
                            "Black Mashroom",
                            "Broccoli",
                            "Cabbage",
                            "Capsicum",
                            "Carrot",
                            "Celery",
                            "Colour Capsicum",
                            "Coriander Fresh",
                            "Cucumber",
                            "Freesi",
                            "Fresh Basil",
                            "Fresh Beans",
                            "Fresh Leek",
                            "Fresh Mushroom",
                            "Fresh Tarragon",
                            "Iceberg",
                            "Lemon",
                            "Lolo Rosso",
                            "Oak Leave",
                            "Onion",
                            "Parsley",
                            "Potato",
                            "Red Bird Chilli",
                            "Red Cabbage",
                            "Romaine Leaves",
                            "Soya Vegetable",
                            "Spinach",
                            "Tomato",
                            "Zucchinni",
                        ],
                    },
                    {
                        "name": "CANNED ITEMS",
                        "items": [
                            "Anchovies Fish",
                            "Artichoke",
                            "Black Olives 03kg",
                            "Capers A green",
                            "Green Olives",
                            "Green pepper corn",
                            "Jalapeno Slice delsol",
                            "Lui tomato paste",
                            "Mushroom 3 KG",
                            "Peeled Tomato Mara",
                            "Pineapple Slice Delmonte",
                            "Pink Pepper Corn",
                            "Sundried Tomato Paste",
                        ],
                    },
                    {
                        "name": "OIL_VINEGAR",
                        "items": [
                            "Balsalmic Vinegar",
                            "Corn Oil",
                            "Dalda Oil",
                            "Extra Virgin Oil Borges",
                            "Fry All Oil",
                            "Grape Whte Wine Vinegar",
                            "Olive oil olio",
                            "Sesame Oil 700ml",
                        ],
                    },
                    {
                        "name": "DAIRY",
                        "items": [
                            "Blue Cheese Castello",
                            "Cheddar Cheese farmGold",
                            "Cheese Slice FarmGold",
                            "Eggs",
                            "Feta Cheese",
                            "Fresh Cream",
                            "Mayonnaise Best Food",
                            "Milk Nestle",
                            "Mozerella Cheese 02.3kg INCOLAC",
                            "Cream Nestle",
                            "Parmesan Cheese",
                            "Puck Cream Cheese 910Gm",
                            "White Butter",
                            "Yellow Butter",
                        ],
                    },
                    {
                        "name": "BAKERY",
                        "items": [
                            "Bread crumb (Uncle Barn`s)",
                            "Burger Bun Seeded",
                            "Butter puff pastry",
                            "Dinner Roll",
                            "French Bread",
                            "Sandwach Bread White",
                            "Sandwich Bread Brown",
                        ],
                    },
                    {
                        "name": "SEASONING _ SPICES",
                        "items": [
                            "Black pepper National",
                            "Black Pepper whole",
                            "Chicken Cube",
                            "Chicken Powder 1 Kg",
                            "Crush Chilli Red",
                            "Dry Tarragon",
                            "Garlic Powder",
                            "Icing Sugar",
                            "katchry Powder",
                            "Oregano Gyma",
                            "Paprika powder",
                            "Rosemarry Gyma",
                            "Salt National",
                            "Sesame Seed (TILL)",
                            "Thyme Gyma",
                            "Tikka Masala National 50gm",
                            "White Pepper powder",
                        ],
                    },
                    {
                        "name": "SAUCES",
                        "items": [
                            "Bar B Q Sauce Knor",
                            "Chilli Garlic Sauce Knor",
                            "Chilli Sauce Key 750ml",
                            "Classic Brown sauce Knor",
                            "Demi Glace Knor",
                            "Dijon Mustered Gyma",
                            "Honey Salman",
                            "Hot souce",
                            "Lemon juice (Mitchells)",
                            "Orange Juice Nestle",
                            "Sambal Oelek Chilli Yeo's",
                            "Soya Sauce Key",
                            "Tabasco 59ml",
                            "Tomato Ketchup Knore",
                            "Whole Grain Mustard Gyma",
                            "Worcestershire sauce",
                            "Siricha Hot Sauces",
                            "Yellow mustard French's",
                        ],
                    },
                    {
                        "name": "PASTA _  FLOUR",
                        "items": [
                            "Bow Tie Pasta",
                            "Corn Flour Rafhan",
                            "Elbow Macaroni",
                            "Fettuccine Pasta",
                            "Flour",
                            "French Fries",
                            "Fusilli Pasta",
                            "Penne pasta",
                            "Risotto Rice Arbioro",
                            "Spaghetti",
                            "Vermicilli Rice",
                        ],
                    },
                    {
                        "name": "OTHER ITEMS",
                        "items": [
                            "Cling Film 45cm",
                            "Aluminium Foil",
                            "Tooth Pick",
                            "Castic Soda",
                            "M.R.D Sticker",
                            "Bamboo Sticks",
                            "Face Mask",
                            "Cap Hair Net",
                            "Plastic Gloves",
                            "Whole skin Chicekn",
                            "Jumbo Roll",
                        ],
                    },
                ],
            },
            {
                "category": "Bar Section",
                "subcategories": [
                    {
                        "name": "SODA _ WATER",
                        "items": [
                            "Pepsi 250ml",
                            "Diet Pepsi",
                            "Mirinda 250ml",
                            "Mineral Water Large 1.5ltrs",
                            "Mountain Dew",
                            "Mineral Water Small 0.5ltrs",
                            "Nestle Water 19LTRS",
                            "Perrier water",
                            "Red Bull 250Ml",
                            "7Up Can 250ml",
                            "7up 1.5 ltr",
                            "7up Zero can 250ml",
                        ],
                    },
                    {
                        "name": "JUICES",
                        "items": [
                            "Apple Juice Nestle",
                            "Chaunsa Juice Nestle",
                            "Lemon juice (Mitchells)",
                            "Lime Cordial Juice Mitchells",
                            "Orange Juice Nestle",
                            "Peach Juice Nestle",
                            "Pineapple Juice Delmonte",
                            "Pomegranate Juice Nestle",
                            "Red Grap Juice Nestle",
                        ],
                    },
                    {
                        "name": "SYRUPS",
                        "items": [
                            "Butterscotch Syrup Routin",
                            "Caramel Syrup Hershey's",
                            "Chocolate Syrup Hershey's",
                            "Coconut Syrup Fabri",
                            "Grandine Syrup Fabri",
                            "Hazelnut Syrup Routin",
                            "Irish Cream Syrup Routin",
                            "Kiwi Syrup Monin",
                            "Peach Mixy Fruit Fabbri",
                            "Pineapple Syrup Fabri",
                            "Raspberry Syrup Fabri",
                            "Strawberry Syrup Hershey's",
                            "Tropical Blue Syrup Fabri",
                            "Vanilla Syrup Routin",
                        ],
                    },
                    {
                        "name": "DAIRY",
                        "items": [
                            "Strawberry Ice Cream Hico",
                            "Vanilla Ice Cream Hico",
                            "Chocolate Ice Cream Hico",
                            "Cream Nestle",
                            "Prema Yogurt",
                            "Prema Milk",
                        ],
                    },
                    {
                        "name": "FRUITS _ VEGETABLES",
                        "items": [
                            "Apple",
                            "Banana",
                            "Falsa",
                            "Lemon",
                            "Mango",
                            "Mint",
                            "Orange",
                            "Peach",
                            "Pomegranate",
                            "Strawberry",
                            "Water Melon",
                        ],
                    },
                    {
                        "name": "TEA _ COFFEE",
                        "items": [
                            "Black Salt",
                            "Brown Sugar Sachets",
                            "Candrel Sachets",
                            "Coconut Powder Santan",
                            "English Breakfast Tea Twining",
                            "Every Day Sachets",
                            "Green Tea Twining",
                            "Green Tea Twining Lemon",
                            "Jasmine Tea",
                            "Lipton Tea Bag",
                            "Nescafe",
                            "Nova Espresso Coffee Beans",
                            "Salt National",
                            "Sugar Plain Meethi",
                            "Cardamom Powder",
                            "White Sugar Sachets",
                        ],
                    },
                    {
                        "name": "CANNED ITEMS",
                        "items": [
                            "BlueBerry Filling AG",
                            "Peach Slice Harvest",
                            "Pineapple Slice Delmonte",
                            "Strawberry Filling AG",
                        ],
                    },
                    {
                        "name": "CHOC _ BISCUITS",
                        "items": [
                            "After Eight Nestle",
                            "Bounty Chocolate",
                            "Choco Waffle Sticks",
                            "Kit Kat Chocolate",
                            "M & M Chocolate",
                            "Nutella Chocolate",
                            "Oreo Biscuit",
                            "Wheat Biscuite",
                        ],
                    },
                    {
                        "name": "STRAWS",
                        "items": [
                            "Magic Straw",
                            "Straw Simple",
                            "Spoon Straw",
                            "Umbrella Straw",
                        ],
                    },
                    {
                        "name": "OTHER ITEMS",
                        "items": [
                            "Almond",
                            "Cashew Nuts",
                            "Cling Film 45cm",
                            "Cocktail Glass",
                            "Cutting Board",
                            "Cutting Knife",
                            "Honey Salman",
                            "Honey Suebee",
                            "Ice Cubes",
                            "Peanut Butter",
                            "Plastic Gloves",
                            "Squeezer",
                            "Stainer",
                            "T/A Coffee Cups",
                            "T/A Cold Cup",
                            "Walnut Giri",
                        ],
                    },
                ],
            },
            {
                "category": "Front of House Section",
                "subcategories": [
                    {
                        "name": "CLEANING SUPPLIES",
                        "items": [
                            "Blue Freshens",
                            "Dishwashing Liquid",
                            "Duster",
                            "Floor Cleaner",
                            "Glint Glass Cleaner Insta",
                            "Hand Wash Liquid",
                            "Max Long Bar",
                            "Mortein Spray",
                            "Phynile Liquid",
                            "Plastic Gloves",
                            "Scotch Brite",
                            "Steel wool JALI",
                            "Surf Bonus",
                            "Toilet Roll",
                            "Towel",
                            "Wood Polish Pledge",
                        ],
                    },
                    {
                        "name": "SAUCE - BOTTLES -  MILK",
                        "items": [
                            "Chilli Garlic Sauce Knor",
                            "Tomato Ketchup Knore",
                            "Tabasco 59ml",
                            "Lipton Tea",
                            "Milk Nestle",
                            "Sugar",
                            "Heinz Tomato Ketchup",
                            "Yellow Mustard Tube",
                            "H.P Sauce",
                        ],
                    },
                    {
                        "name": "LP22",
                        "items": [
                            "T/A Bag",
                            "Plastic Spoon",
                            "Plastic Fork",
                            "Tomato Ketchup sachets Knor",
                            "Chilli Garlic Sachets Knor",
                        ],
                    },
                    {
                        "name": "OTHER SUPPLIES",
                        "items": [
                            "Air Freshener",
                            "Garbage Bag",
                            "Hygeine Tissue",
                            "KOT Books",
                            "Logo Napkins (Table Tissue)",
                            "Scotch Tape",
                            "Soup Bowl",
                            "T/A Remican",
                            "Toothpicks",
                        ],
                    },
                ],
            },
            {
                "category": "Asian Fusion Section",
                "subcategories": [
                    {
                        "name": "MEATS",
                        "items": [
                            "Chicken Breast K&N's",
                            "Chicken Boneless Local",
                            "Chicken Wings Local",
                            "Chicken Neck Local",
                            "Leatherjacket Fish",
                            "Prawns 11/15",
                            "Fish Pangasius",
                            "Beef Undercut",
                        ],
                    },
                    {
                        "name": "VEGETABLES",
                        "items": [
                            "Lemon Grass",
                            "Beet Root",
                            "Cabbage",
                            "Capsicum",
                            "Carrot",
                            "Colour Capsicum",
                            "Coriander Fresh",
                            "Fresh Mushroom",
                            "Garlic",
                            "Ginger",
                            "Green Chilli",
                            "Green onion",
                            "Lemon",
                            "Onion",
                            "Potato",
                            "Red Bird Chilli",
                            "Red Cabbage",
                            "Red Chilli Whole",
                            "Tomato",
                            "Zucchini",
                        ],
                    },
                    {
                        "name": "SAUCE _ PASTE",
                        "items": [
                            "Black  Mushroom",
                            "Chilli Paste Soya Bean",
                            "Roll Patti",
                            "Fish Sauce Melabone",
                            "H.P Sauce",
                            "Sriracha Holy Basil Sauce",
                            "Hoisin Sauce",
                            "Honey Salman",
                            "Sambal Oelek Chilli Paste",
                            "Hot & Sour Paste China Store",
                            "Imli",
                            "kung Pao Paste",
                            "Lemon juice (Mitchells)",
                            "Oyster Sauce Mama Sita",
                            "Soya Sauce Dark China Store",
                            "Soya Sauce Lite",
                            "Suree Sweet Sauce",
                            "Sichuan Paste",
                            "Thai Chilli Sauce",
                            "Tabasco 59ml",
                            "Tomato Ketchup Knore",
                            "Tomato Ketchup Shezan",
                            "Wasabi Tube",
                        ],
                    },
                    {
                        "name": "POWDER _ CRUMBS",
                        "items": [
                            "Black pepper National",
                            "Bread crumb (Uncle Barn`s)",
                            "Chicken Powder Knor",
                            "Salt National",
                            "Sesame Seed (TILL)",
                            "China Salt",
                            "Food Colour Red",
                            "Food Colour Yellow",
                            "Coconut Powder Santan",
                            "Corn Flour Rafhan",
                            "Meat Tenderizer",
                            "Shakkar",
                            "Sugar",
                            "Tempura Flour",
                            "Wasabi Powder",
                            "White Pepper powder",
                        ],
                    },
                    {
                        "name": "DAIRY",
                        "items": [
                            "Eggs",
                            "Milk Nestle",
                            "Puck Cream Cheese 910Gm",
                            "US Mayonnaise AG",
                        ],
                    },
                    {
                        "name": "NUTS _ RICE",
                        "items": ["CashewNut", "Peanut Plain", "Rice Noodle", "Rice"],
                    },
                    {
                        "name": "OIL _ VINEGAR",
                        "items": [
                            "Black Vinegar China Store",
                            "Dalda Oil",
                            "Fry All Oil",
                            "Food Wine China Store",
                            "Red Wine Vineger",
                            "Sesame Oil 700ml",
                            "Rice Vinegar",
                            "Vinegar White Shezan",
                        ],
                    },
                    {
                        "name": "CANNED ITEMS",
                        "items": [
                            "Baby Corn",
                            "Bamboo shoot",
                            "Mushroom 3 KG",
                            "Pineapple Slice Delmonte",
                            "Potato Starch",
                            "Sweet Corn Choice",
                        ],
                    },
                    {
                        "name": "OTHER ITEMS",
                        "items": [
                            "Cling Film 45cm",
                            "Face Mask",
                            "M.R.D Sticker",
                            "Cap Hair Net",
                            "Rubber Gloves",
                            "Duster",
                        ],
                    },
                ],
            },
            {
                "category": "Pizza Section",
                "subcategories": [
                    {
                        "name": "MEAT",
                        "items": [
                            "Chicken Boneless Local",
                            "Frank Furter Chicken Sauceges",
                        ],
                    },
                    {
                        "name": "CHEESE",
                        "items": [
                            "Mozerella Cheese 02.3kg INCOLAC",
                            "cheddar cheese Cheese farmGold",
                        ],
                    },
                    {
                        "name": "CANNED ITEMS",
                        "items": [
                            "Lui  tomato paste",
                            "Black Olives 03kg",
                            "Mushroom 3 KG",
                        ],
                    },
                    {"name": "DAIRY", "items": ["Nestle Yogurt (500gm)"]},
                    {
                        "name": "FRESH VEGETABLES",
                        "items": ["Capsicum", "Imported Capsicum", "Tomato", "Onion"],
                    },
                    {
                        "name": "SEASONING _ POWDER",
                        "items": [
                            "Blacke Pepper Powder National",
                            "Tikka Masala National 50gm",
                            "Icing Sugar",
                            "Ekka Powder",
                            "Salt National",
                            "Yeast (Saf Instant)",
                            "Pizza Flour",
                            "Every Day Milk Powder 01kg",
                        ],
                    },
                    {"name": "OILS", "items": ["Dalda Oil"]},
                    {
                        "name": "OTHER ITEMS",
                        "items": [
                            "Tomato Ketchup sachets Knor",
                            "Chilli Sauce Key 750ml",
                            "Plastic Gloves",
                            "Peproni Slice K&N's",
                            "Hot Sauce",
                        ],
                    },
                ],
            },
            {
                "category": "Dessert Section",
                "subcategories": [
                    {
                        "name": "DAIRY",
                        "items": [
                            "Eggs",
                            "Nur Pur Butter",
                            "Cream Nestle",
                            "Milk Nestle",
                            "Philadelphia Cheese",
                            "Richi's Cream",
                            "Puck Cream Cheese 910Gm",
                            "Vanilla Ice Cream Hico",
                        ],
                    },
                    {
                        "name": "CHOCOLATE _ BISCUITS",
                        "items": [
                            "Zeelandia Chocolate",
                            "Milky Chocolate",
                            "Malaysian ChocolateSelbourn",
                            "Local Chocolate",
                            "Nutella Chocolate",
                            "White Chocolate",
                            "Cho Cho Chocolate",
                            "Lindt Dark Chocolate",
                            "Candi Biscuit",
                            "Oreo Biscuit",
                            "Lotous",
                            "Wheat Biscuite",
                        ],
                    },
                    {"name": "SYRUPS", "items": ["Chocolate Syrup", "Caramel Syrup"]},
                    {"name": "FRUITS", "items": ["Banana", "Kishmish/Sogee"]},
                    {
                        "name": "POWDER _ FLOUR",
                        "items": [
                            "Gelatine Powder Rosemore",
                            "Nestle Milo",
                            "Cocoa Powder",
                            "Salt National",
                            "Brown Sugar",
                            "Yeast (Saf Instant)",
                            "Ekka Powder",
                            "Baking Powder",
                            "Sugar",
                            "Caster Sugar",
                            "Flour",
                            "Icing Sugar",
                        ],
                    },
                    {"name": "OILS", "items": ["Dalda Oil", "Dalda Ghee"]},
                    {
                        "name": "CANNED ITEMS",
                        "items": [
                            "Red Cherry Glaze",
                            "Polac Condensed Milk",
                            "Strawberry Filling AG",
                            "BlueBerry Filling AG",
                        ],
                    },
                    {
                        "name": "OTHER ITEMS",
                        "items": [
                            "Cling Film 45cm",
                            "M.R.D Sticker",
                            "Duster",
                            "Aluminium Foil",
                            "T/A Ice Cream Cup",
                            "Butter Paper",
                            "Cake Board",
                            "Jelly",
                            "King Milk",
                            "Chocolate Chip",
                            "Sandwich White Bread",
                            "White Butter",
                        ],
                    },
                ],
            },
            {
                "category": "Staff Food Section",
                "subcategories": [
                    {
                        "name": "MEATS - DAAL",
                        "items": ["Staff Food Chicken", "Staff Food Daal"],
                    },
                    {
                        "name": "VEGETABLES",
                        "items": [
                            "Onion",
                            "Green Chilli",
                            "Cauli Flower",
                            "Coriander Fresh",
                            "Ginger",
                            "Cabbage",
                            "Capsicum",
                            "Tomato",
                            "Garlic",
                        ],
                    },
                    {
                        "name": "SEASONING _ SPICES",
                        "items": [
                            "Salt National",
                            "Red Chilli Powder",
                            "Zeera White whole",
                            "Kasuri Methi",
                            "Food Colour",
                            "Biryani Masala National",
                            "Garam Masala Powder",
                            "Turmeric Powder (Haldi)",
                        ],
                    },
                    {
                        "name": "OTHER ITEMS",
                        "items": [
                            "Lipton Tea",
                            "Dalda Oil",
                            "Yogurt Local",
                            "Rice Local Staff Food",
                        ],
                    },
                ],
            },
        ]

        items = []
        uom_map = {
            "MEATS": uoms[0],
            "VEGETABLES": uoms[0],
            "DAIRY": uoms[3],
            "OIL/VINEGAR": uoms[3],
            "MEAT": uoms[0],
            "FRESH VEGETABLES": uoms[0],
            "POWDER / FLOUR": uoms[1],
        }
        default_uom = uoms[2]  # pcs

        for cat_data in inventory_hierarchy:
            parent_cat, _ = InventoryCategory.objects.get_or_create(
                name=cat_data["category"]
            )
            for sub_data in cat_data["subcategories"]:
                sub_name = sub_data["name"]
                sub_cat, _ = InventoryCategory.objects.get_or_create(
                    name=sub_name, parent_category=parent_cat
                )
                unit = uom_map.get(sub_data["name"], default_uom)

                for name in sub_data["items"]:
                    clean_readable_name = " ".join(name.split())
                    clean_name = "".join(
                        [c for c in clean_readable_name if c.isalnum()]
                    ).upper()

                    item = InventoryItem.objects.filter(
                        name=clean_readable_name
                    ).first()
                    if not item:
                        base_sku_prefix = (
                            f"INV-{sub_data['name'][:3]}-{clean_name[:40]}"
                        )
                        sku_base = base_sku_prefix
                        counter = 1
                        while InventoryItem.objects.filter(sku=sku_base).exists():
                            sku_base = f"{base_sku_prefix}-{counter}"
                            counter += 1

                        # The barcode is deliberately left blank: InventoryItem
                        # generates a unique 8-character one on save, which is
                        # what the column is sized for. This used to pass
                        # barcode=f"BC-{sku_base}" — an SKU-length string into a
                        # varchar(8) — so `manage.py setup_dev` died with
                        # "value too long for type character varying(8)" and the
                        # project could not be seeded at all.
                        item = InventoryItem.objects.create(
                            name=clean_readable_name,
                            sku=sku_base,
                            section=parent_cat,
                            category=sub_cat,
                            unit=unit,
                        )

                    items.append(item)
        return items

    def create_products(self, branches):
        products_data = [
            {
                "product_category": "Asian Fusion",
                "product_name": "Arcadian Chili Chicken with Garlic Rice",
                "product_id": "442",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Arcadian Special Crispy Chicken with Rice",
                "product_id": "382",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Arcadian Special Crispy Fish",
                "product_id": "25051",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Arcadian Special Soup",
                "product_id": "6",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Bai Ze Chicken",
                "product_id": "348",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Basil Leaf Beef",
                "product_id": "368",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Basil Leaf Chicken",
                "product_id": "361",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Basil Leaf Fish",
                "product_id": "362",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Basil Leaf Prawn",
                "product_id": "25065",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Batter Fried Prawns",
                "product_id": "1",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Beef Cashew nut with Rice",
                "product_id": "10639",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Beef Chili Dry with Rice",
                "product_id": "24",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Beef Chowmein",
                "product_id": "10633",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Black Pepper Beef with Rice",
                "product_id": "10640",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Black Pepper Chicken with Rice",
                "product_id": "11",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Black Pepper Fish with Rice",
                "product_id": "197",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Breaded Butterfly Prawns",
                "product_id": "443",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Chicken Cashew nut with Rice",
                "product_id": "29",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Chicken Chili Dry with Rice",
                "product_id": "14",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Chicken Chowmein",
                "product_id": "299",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Chicken Corn Soup",
                "product_id": "4",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Chicken Drum Sticks 6 PC.",
                "product_id": "13",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Chicken Manchurian with Rice",
                "product_id": "10",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Chicken Noodle Soup",
                "product_id": "25021",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Chicken Spring Rolls",
                "product_id": "10554",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "CHICKEN TARO",
                "product_id": "25299",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Clear Chicken and Vegetable Soup",
                "product_id": "232",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Crispy Dragon Beef",
                "product_id": "10589",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Crispy Honey Chicken",
                "product_id": "25049",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Crispy Honey Chili Potatoes",
                "product_id": "25045",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Crispy Naga Chicken",
                "product_id": "10590",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Crispy Panko Prawns",
                "product_id": "25029",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Crispy Sesame Beef",
                "product_id": "10626",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Diablo Noodles Beef",
                "product_id": "453",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Diablo Noodles Chicken",
                "product_id": "427",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Diablo Noodles Prawns",
                "product_id": "428",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Dynamite Prawns",
                "product_id": "227",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Egg Fried Rice",
                "product_id": "196",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Finger Fish",
                "product_id": "238",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Fish Chilli Dry with Rice",
                "product_id": "22",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Fish n Chips",
                "product_id": "237",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Garlic Rice",
                "product_id": "341",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "General Tso Chicken",
                "product_id": "439",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Grilled Chicken Shashlik",
                "product_id": "25076",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "HALF PORTION FISH",
                "product_id": "25077",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Honey Wings",
                "product_id": "190",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Hot & Sour Chicken WITH RICE",
                "product_id": "10634",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Hot & Sour Fish",
                "product_id": "10635",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Hot & Sour Prawns",
                "product_id": "10636",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Hot & Sour Soup",
                "product_id": "5",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Hot Garlic Chicken with Rice",
                "product_id": "7",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Hot Garlic Fish with Rice",
                "product_id": "19",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Hot Garlic Prawns with Rice",
                "product_id": "15",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Inferno Soup",
                "product_id": "25022",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Kung Pao Chicken with Rice",
                "product_id": "8",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Kung Pao Fish with Rice",
                "product_id": "23",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Kung Pao Prawn with Rice",
                "product_id": "18",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Oyster Sauce Beef With Rice",
                "product_id": "25",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Oyster Sauce Chicken With Rice",
                "product_id": "10637",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Oyster Sauce Prawns With Rice",
                "product_id": "10638",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Pad Thai Beef",
                "product_id": "10583",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Pad Thai Chicken",
                "product_id": "10582",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Pad Thai Prawns",
                "product_id": "10584",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Pataya Beef",
                "product_id": "25050",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Plain White Rice",
                "product_id": "25017",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Prawn Cashew nut with Rice",
                "product_id": "31",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Prawns Chili Dry",
                "product_id": "307",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Prawns Chowmein",
                "product_id": "300",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Red Dragon Beef with Rice",
                "product_id": "240",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Red Dragon Chicken with Rice",
                "product_id": "216",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Red Dragon Fish with Rice",
                "product_id": "220",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Red Dragon Prawns with Rice",
                "product_id": "234",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Red Hot & Sour Soup",
                "product_id": "10546",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "RISSOTO RICE",
                "product_id": "25460",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "SAMURAI CHICKEN",
                "product_id": "25089",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sichuan Chicken with Rice",
                "product_id": "12",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Spicy Panko Chicken",
                "product_id": "25030",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sriracha Basil Beef with Rice",
                "product_id": "377",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sriracha Basil Chicken with Rice",
                "product_id": "376",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "SRIRACHA BASIL FISH",
                "product_id": "25440",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sriracha Basil Fish with Rice",
                "product_id": "380",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sriracha Basil Prawns with Rice",
                "product_id": "381",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sun Tzu Beef",
                "product_id": "429",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sun Tzu Chicken",
                "product_id": "355",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sun Tzu Fish",
                "product_id": "371",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sun Tzu Prawns",
                "product_id": "357",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sweet \u2018n\u2019 Sour Chicken with Rice",
                "product_id": "9",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sweet \u2018n\u2019 Sour Fish with Rice",
                "product_id": "21",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Sweet \u2018n\u2019 Sour Prawn with Rice",
                "product_id": "17",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Szechuan Fish with Rice",
                "product_id": "20",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Szechuan Prawn with Rice",
                "product_id": "16",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Szechuan Soup",
                "product_id": "333",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Amazon Beef with Garlic Rice",
                "product_id": "375",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Amazon Chicken with Garlic Rice",
                "product_id": "369",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Amazon Prawns",
                "product_id": "430",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "THAI CHILLI DRY BEEF",
                "product_id": "25093",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "THAI CHILLI DRY CHICKEN",
                "product_id": "25092",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "THAI CHILLI DRY FISH",
                "product_id": "25094",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "THAI CHILLI DRY PRAWNS",
                "product_id": "25095",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Crispy Chicken Salad",
                "product_id": "403",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Fiery Hot Beef",
                "product_id": "359",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Fiery Hot Chicken",
                "product_id": "352",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Fiery Hot Fish",
                "product_id": "379",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Fiery Hot Prawns",
                "product_id": "356",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Hot Basil Beef",
                "product_id": "25047",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Hot Basil Chicken",
                "product_id": "25046",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "THAI HOT BASIL FISH",
                "product_id": "25096",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Hot Basil Prawn",
                "product_id": "25048",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Thai Sweet Chili Wings",
                "product_id": "423",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Tom Yum Soup",
                "product_id": "10547",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Volcanic Pickled Chicken",
                "product_id": "10588",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Wasabi Prawns",
                "product_id": "37",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Weaveball Prawns",
                "product_id": "350",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "Wok Fried Vegetables with Rice",
                "product_id": "406",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "WuHu Special Chicken",
                "product_id": "10644",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "WuHu Special Fish",
                "product_id": "10627",
            },
            {
                "product_category": "Asian Fusion",
                "product_name": "WuHu Special Prawn",
                "product_id": "25008",
            },
            {"product_category": "Bar", "product_name": "7Up", "product_id": "200"},
            {
                "product_category": "Bar",
                "product_name": "7up Diet",
                "product_id": "168",
            },
            {
                "product_category": "Bar",
                "product_name": "Americano",
                "product_id": "139",
            },
            {
                "product_category": "Bar",
                "product_name": "Angel Kiss",
                "product_id": "401",
            },
            {
                "product_category": "Bar",
                "product_name": "Angel surprise",
                "product_id": "125",
            },
            {
                "product_category": "Bar",
                "product_name": "Apple Mint",
                "product_id": "10628",
            },
            {
                "product_category": "Bar",
                "product_name": "Arcadian Special bully",
                "product_id": "151",
            },
            {
                "product_category": "Bar",
                "product_name": "Blue Lagoon",
                "product_id": "336",
            },
            {
                "product_category": "Bar",
                "product_name": "Butterscotch",
                "product_id": "135",
            },
            {
                "product_category": "Bar",
                "product_name": "Cappuccino",
                "product_id": "131",
            },
            {"product_category": "Bar", "product_name": "Caramel", "product_id": "133"},
            {
                "product_category": "Bar",
                "product_name": "Chocolate",
                "product_id": "137",
            },
            {
                "product_category": "Bar",
                "product_name": "Chocolate Brownie Shake",
                "product_id": "420",
            },
            {
                "product_category": "Bar",
                "product_name": "Chocolate Shake",
                "product_id": "154",
            },
            {
                "product_category": "Bar",
                "product_name": "Classic Pina colada",
                "product_id": "121",
            },
            {
                "product_category": "Bar",
                "product_name": "Club Soda",
                "product_id": "211",
            },
            {"product_category": "Bar", "product_name": "Coke", "product_id": "342"},
            {
                "product_category": "Bar",
                "product_name": "Cold Coffee",
                "product_id": "142",
            },
            {
                "product_category": "Bar",
                "product_name": "Death by chocolate",
                "product_id": "126",
            },
            {
                "product_category": "Bar",
                "product_name": "Diet Coke",
                "product_id": "346",
            },
            {
                "product_category": "Bar",
                "product_name": "Double Espresso",
                "product_id": "130",
            },
            {
                "product_category": "Bar",
                "product_name": "Earl Gray Tea",
                "product_id": "160",
            },
            {
                "product_category": "Bar",
                "product_name": "Electric Lemonade",
                "product_id": "419",
            },
            {
                "product_category": "Bar",
                "product_name": "English Breakfast Tea",
                "product_id": "159",
            },
            {
                "product_category": "Bar",
                "product_name": "Espresso",
                "product_id": "129",
            },
            {"product_category": "Bar", "product_name": "Fanta", "product_id": "344"},
            {
                "product_category": "Bar",
                "product_name": "Ferrari bully",
                "product_id": "150",
            },
            {
                "product_category": "Bar",
                "product_name": "Fresh Lime With Soft Drink",
                "product_id": "169",
            },
            {
                "product_category": "Bar",
                "product_name": "Fresh Lime With ZERO",
                "product_id": "25461",
            },
            {
                "product_category": "Bar",
                "product_name": "Green Tea",
                "product_id": "157",
            },
            {
                "product_category": "Bar",
                "product_name": "Hazelnut",
                "product_id": "134",
            },
            {
                "product_category": "Bar",
                "product_name": "Iced Tea Lime",
                "product_id": "163",
            },
            {
                "product_category": "Bar",
                "product_name": "Iced Tea Peach",
                "product_id": "162",
            },
            {
                "product_category": "Bar",
                "product_name": "Iced Tea Raspberry",
                "product_id": "164",
            },
            {
                "product_category": "Bar",
                "product_name": "Irish Cream",
                "product_id": "138",
            },
            {
                "product_category": "Bar",
                "product_name": "Jasmine Tea",
                "product_id": "158",
            },
            {
                "product_category": "Bar",
                "product_name": "Kit Kat Shake",
                "product_id": "421",
            },
            {"product_category": "Bar", "product_name": "Latte", "product_id": "132"},
            {
                "product_category": "Bar",
                "product_name": "Lemonade",
                "product_id": "270",
            },
            {
                "product_category": "Bar",
                "product_name": "Lightening Shot",
                "product_id": "114",
            },
            {
                "product_category": "Bar",
                "product_name": "Lovely Day",
                "product_id": "308",
            },
            {
                "product_category": "Bar",
                "product_name": "Lover\u2019s Spat",
                "product_id": "115",
            },
            {
                "product_category": "Bar",
                "product_name": "Mango Shake (Fresh)",
                "product_id": "305",
            },
            {
                "product_category": "Bar",
                "product_name": "Margarita Blue Berry",
                "product_id": "264",
            },
            {
                "product_category": "Bar",
                "product_name": "Margarita Lime",
                "product_id": "261",
            },
            {
                "product_category": "Bar",
                "product_name": "Margarita Mint",
                "product_id": "263",
            },
            {
                "product_category": "Bar",
                "product_name": "Margarita Peach",
                "product_id": "262",
            },
            {
                "product_category": "Bar",
                "product_name": "Margarita Strawbery",
                "product_id": "127",
            },
            {
                "product_category": "Bar",
                "product_name": "MARINDA",
                "product_id": "25303",
            },
            {
                "product_category": "Bar",
                "product_name": "Mint Chocolate Blast",
                "product_id": "422",
            },
            {"product_category": "Bar", "product_name": "Mojito", "product_id": "119"},
            {
                "product_category": "Bar",
                "product_name": "Moon Rocker",
                "product_id": "117",
            },
            {
                "product_category": "Bar",
                "product_name": "Mountain Dew",
                "product_id": "231",
            },
            {
                "product_category": "Bar",
                "product_name": "Orange Italian Soda",
                "product_id": "25056",
            },
            {
                "product_category": "Bar",
                "product_name": "Oreo Pleasure",
                "product_id": "122",
            },
            {
                "product_category": "Bar",
                "product_name": "P.B Mania",
                "product_id": "449",
            },
            {
                "product_category": "Bar",
                "product_name": "PASSIONFRUIT MOJITO",
                "product_id": "25315",
            },
            {"product_category": "Bar", "product_name": "Pepsi", "product_id": "167"},
            {
                "product_category": "Bar",
                "product_name": "Pepsi Diet",
                "product_id": "242",
            },
            {
                "product_category": "Bar",
                "product_name": "PERRIER 750ML",
                "product_id": "25468",
            },
            {
                "product_category": "Bar",
                "product_name": "Perrier Carbonated Water",
                "product_id": "212",
            },
            {
                "product_category": "Bar",
                "product_name": "Pink Barbie",
                "product_id": "10631",
            },
            {
                "product_category": "Bar",
                "product_name": "Pure Water Large",
                "product_id": "166",
            },
            {
                "product_category": "Bar",
                "product_name": "Pure Water Small",
                "product_id": "165",
            },
            {
                "product_category": "Bar",
                "product_name": "Purple Heaven",
                "product_id": "116",
            },
            {
                "product_category": "Bar",
                "product_name": "Red Bull (250ml)",
                "product_id": "186",
            },
            {
                "product_category": "Bar",
                "product_name": "Salted Caramel Praline Shake",
                "product_id": "25058",
            },
            {
                "product_category": "Bar",
                "product_name": "Seasonal Fresh Juices",
                "product_id": "147",
            },
            {
                "product_category": "Bar",
                "product_name": "Sky bully",
                "product_id": "148",
            },
            {
                "product_category": "Bar",
                "product_name": "Smoothie Apple",
                "product_id": "275",
            },
            {
                "product_category": "Bar",
                "product_name": "Smoothie Banana",
                "product_id": "274",
            },
            {
                "product_category": "Bar",
                "product_name": "Smoothie Mango",
                "product_id": "277",
            },
            {
                "product_category": "Bar",
                "product_name": "Smoothie Orange",
                "product_id": "276",
            },
            {
                "product_category": "Bar",
                "product_name": "Smoothie Peach",
                "product_id": "273",
            },
            {
                "product_category": "Bar",
                "product_name": "Smoothie Strawbery",
                "product_id": "272",
            },
            {
                "product_category": "Bar",
                "product_name": "Smoothies",
                "product_id": "128",
            },
            {"product_category": "Bar", "product_name": "Sprite", "product_id": "343"},
            {
                "product_category": "Bar",
                "product_name": "Sprite Zero",
                "product_id": "345",
            },
            {
                "product_category": "Bar",
                "product_name": "Strawberry bully",
                "product_id": "152",
            },
            {
                "product_category": "Bar",
                "product_name": "Strawberry Kiwi Chiller",
                "product_id": "25057",
            },
            {
                "product_category": "Bar",
                "product_name": "Strawberry Melon Mojito",
                "product_id": "25055",
            },
            {
                "product_category": "Bar",
                "product_name": "Strawberry Shake",
                "product_id": "156",
            },
            {
                "product_category": "Bar",
                "product_name": "TESTING DRINK",
                "product_id": "25300",
            },
            {"product_category": "Bar", "product_name": "Vanilla", "product_id": "136"},
            {
                "product_category": "Bar",
                "product_name": "Vanilla Shake",
                "product_id": "153",
            },
            {
                "product_category": "Bar",
                "product_name": "Zing Toaster bully",
                "product_id": "149",
            },
            {
                "product_category": "Continental",
                "product_name": "Arcadian Special Italiano Pasta",
                "product_id": "185",
            },
            {
                "product_category": "Continental",
                "product_name": "Arcadian Special Sandwich",
                "product_id": "451",
            },
            {
                "product_category": "Continental",
                "product_name": "BBQ Burger Beef",
                "product_id": "75",
            },
            {
                "product_category": "Continental",
                "product_name": "BBQ Burger Chicken",
                "product_id": "69",
            },
            {
                "product_category": "Continental",
                "product_name": "BBQ Chicken & Turkey Strip Melt",
                "product_id": "243",
            },
            {
                "product_category": "Continental",
                "product_name": "BBQ Wings",
                "product_id": "3",
            },
            {
                "product_category": "Continental",
                "product_name": "Black Pepper Burger Beef",
                "product_id": "76",
            },
            {
                "product_category": "Continental",
                "product_name": "Black Pepper Burger Chicken",
                "product_id": "70",
            },
            {
                "product_category": "Continental",
                "product_name": "Bleu Cheese Steak (Beef)",
                "product_id": "67",
            },
            {
                "product_category": "Continental",
                "product_name": "Bleu Cheese Steak (Chicken)",
                "product_id": "61",
            },
            {
                "product_category": "Continental",
                "product_name": "Buffalo Wings",
                "product_id": "90",
            },
            {
                "product_category": "Continental",
                "product_name": "Cali Salad",
                "product_id": "25024",
            },
            {
                "product_category": "Continental",
                "product_name": "California Ranch Burger",
                "product_id": "10569",
            },
            {
                "product_category": "Continental",
                "product_name": "Chicken Nuggets",
                "product_id": "432",
            },
            {
                "product_category": "Continental",
                "product_name": "Chicken Sliders",
                "product_id": "433",
            },
            {
                "product_category": "Continental",
                "product_name": "Chicken Strips",
                "product_id": "228",
            },
            {
                "product_category": "Continental",
                "product_name": "Classic Chicken Burger",
                "product_id": "444",
            },
            {
                "product_category": "Continental",
                "product_name": "Club Sandwich",
                "product_id": "85",
            },
            {
                "product_category": "Continental",
                "product_name": "Creamy Mushroom Steak (Beef)",
                "product_id": "65",
            },
            {
                "product_category": "Continental",
                "product_name": "Creamy Mushroom Steak (Chicken)",
                "product_id": "59",
            },
            {
                "product_category": "Continental",
                "product_name": "Crispy Batter Chicken",
                "product_id": "25028",
            },
            {
                "product_category": "Continental",
                "product_name": "Crispy Chicken Burger",
                "product_id": "10545",
            },
            {
                "product_category": "Continental",
                "product_name": "Crispy Onion Rings",
                "product_id": "25025",
            },
            {
                "product_category": "Continental",
                "product_name": "Double Trouble",
                "product_id": "10567",
            },
            {
                "product_category": "Continental",
                "product_name": "Extra Cheese",
                "product_id": "180",
            },
            {
                "product_category": "Continental",
                "product_name": "Extra Veggies",
                "product_id": "181",
            },
            {
                "product_category": "Continental",
                "product_name": "Fettuccini Pasta",
                "product_id": "87",
            },
            {
                "product_category": "Continental",
                "product_name": "Fire Hot Steak (Beef)",
                "product_id": "199",
            },
            {
                "product_category": "Continental",
                "product_name": "Fire Hot Steak (Chicken)",
                "product_id": "193",
            },
            {
                "product_category": "Continental",
                "product_name": "French Fries",
                "product_id": "178",
            },
            {
                "product_category": "Continental",
                "product_name": "Garlic Bread",
                "product_id": "10594",
            },
            {
                "product_category": "Continental",
                "product_name": "Garlic Butter Steak",
                "product_id": "25031",
            },
            {
                "product_category": "Continental",
                "product_name": "Green Chili Poppers",
                "product_id": "25027",
            },
            {
                "product_category": "Continental",
                "product_name": "GREEN CHILLI POPPER BURGER",
                "product_id": "25081",
            },
            {
                "product_category": "Continental",
                "product_name": "Grilled Chicken Sandwich",
                "product_id": "84",
            },
            {
                "product_category": "Continental",
                "product_name": "Grilled Fajita Sandwich",
                "product_id": "425",
            },
            {
                "product_category": "Continental",
                "product_name": "Jalapeno Burger Beef",
                "product_id": "78",
            },
            {
                "product_category": "Continental",
                "product_name": "Jalapeno Burger Chicken",
                "product_id": "72",
            },
            {
                "product_category": "Continental",
                "product_name": "Jalapeno Steak (Beef)",
                "product_id": "66",
            },
            {
                "product_category": "Continental",
                "product_name": "Jalapeno Steak (Chicken)",
                "product_id": "60",
            },
            {
                "product_category": "Continental",
                "product_name": "Kids Pasta",
                "product_id": "435",
            },
            {
                "product_category": "Continental",
                "product_name": "Loaded Skillet Fries",
                "product_id": "25018",
            },
            {
                "product_category": "Continental",
                "product_name": "Louisiana Fried Chicken Pasta",
                "product_id": "10579",
            },
            {
                "product_category": "Continental",
                "product_name": "MAC AND CHEESE CHICKEN SANDWICH",
                "product_id": "25080",
            },
            {
                "product_category": "Continental",
                "product_name": "MAC AND CHEESE CHIKEN BURGER",
                "product_id": "25469",
            },
            {
                "product_category": "Continental",
                "product_name": "MAC AND CHEESE STEAK SANDWICH",
                "product_id": "25079",
            },
            {
                "product_category": "Continental",
                "product_name": "Mozzarella Sticks",
                "product_id": "404",
            },
            {
                "product_category": "Continental",
                "product_name": "Mushroom Burger Chicken",
                "product_id": "71",
            },
            {
                "product_category": "Continental",
                "product_name": "NASHVILLE DYNAMITE CHICKEN BURGER",
                "product_id": "25086",
            },
            {
                "product_category": "Continental",
                "product_name": "Open Face Sandwich",
                "product_id": "82",
            },
            {
                "product_category": "Continental",
                "product_name": "Plain Steak (Beef)",
                "product_id": "68",
            },
            {
                "product_category": "Continental",
                "product_name": "Plain Steak (Chicken)",
                "product_id": "62",
            },
            {
                "product_category": "Continental",
                "product_name": "Rattlesnake Pasta",
                "product_id": "86",
            },
            {
                "product_category": "Continental",
                "product_name": "Salsa Beef Sandwich",
                "product_id": "25020",
            },
            {
                "product_category": "Continental",
                "product_name": "Shredded Beef Sliders",
                "product_id": "25064",
            },
            {
                "product_category": "Continental",
                "product_name": "Southwestern Chicken & Shrimp Pasta",
                "product_id": "10619",
            },
            {
                "product_category": "Continental",
                "product_name": "Spicy Chipotle Chicken Pasta",
                "product_id": "10618",
            },
            {
                "product_category": "Continental",
                "product_name": "Spicy Grilled Prawns",
                "product_id": "402",
            },
            {
                "product_category": "Continental",
                "product_name": "Spicy Shitake Steak",
                "product_id": "25032",
            },
            {
                "product_category": "Continental",
                "product_name": "Steak With Black Pepper Sauce (Beef)",
                "product_id": "64",
            },
            {
                "product_category": "Continental",
                "product_name": "Steak With Black Pepper Sauce (Chicken)",
                "product_id": "58",
            },
            {
                "product_category": "Continental",
                "product_name": "STUFF CHEEZY BITES",
                "product_id": "25455",
            },
            {
                "product_category": "Continental",
                "product_name": "Stuffed Chicken Barrels",
                "product_id": "25026",
            },
            {
                "product_category": "Continental",
                "product_name": "Stuffed Jalapeno Cheddar",
                "product_id": "10568",
            },
            {
                "product_category": "Continental",
                "product_name": "Stuffed Peri Chicken",
                "product_id": "416",
            },
            {
                "product_category": "Continental",
                "product_name": "Sweet Pepper Steak Salad",
                "product_id": "25023",
            },
            {
                "product_category": "Continental",
                "product_name": "Texas Barbeque Steak (Beef)",
                "product_id": "63",
            },
            {
                "product_category": "Continental",
                "product_name": "Texas Barbeque Steak (Chicken)",
                "product_id": "57",
            },
            {
                "product_category": "Continental",
                "product_name": "Ultimate Supreme Burger",
                "product_id": "10570",
            },
            {
                "product_category": "DEAL",
                "product_name": "AFTAR BUFFET",
                "product_id": "25456",
            },
            {
                "product_category": "DEAL",
                "product_name": "AFTAR BUFFET KID",
                "product_id": "25457",
            },
            {
                "product_category": "DEAL",
                "product_name": "CHEETAY COMBO",
                "product_id": "25090",
            },
            {
                "product_category": "DEAL",
                "product_name": "COZY FOR 2 DEAL",
                "product_id": "25005",
            },
            {
                "product_category": "DEAL",
                "product_name": "FANTASTIC 4 DEAL",
                "product_id": "25006",
            },
            {
                "product_category": "DEAL",
                "product_name": "FOODIE FAMILY DEAL",
                "product_id": "25007",
            },
            {
                "product_category": "DEAL",
                "product_name": "KING FEAST",
                "product_id": "25082",
            },
            {
                "product_category": "DEAL",
                "product_name": "PARTNER IN CRIME DEAL",
                "product_id": "25002",
            },
            {
                "product_category": "DEAL",
                "product_name": "PIZZA LOVERS DEAL",
                "product_id": "25004",
            },
            {
                "product_category": "DEAL",
                "product_name": "SQUAD MUNCHIN DEAL",
                "product_id": "25003",
            },
            {
                "product_category": "Desserts",
                "product_name": "Blueberry Cheese Cake",
                "product_id": "171",
            },
            {
                "product_category": "Desserts",
                "product_name": "Bread Pudding",
                "product_id": "383",
            },
            {
                "product_category": "Desserts",
                "product_name": "CHOCOLATE OREO CARAMEL PIE",
                "product_id": "25078",
            },
            {
                "product_category": "Desserts",
                "product_name": "Cookie Skillet",
                "product_id": "10552",
            },
            {
                "product_category": "Desserts",
                "product_name": "Deep Fried Ice cream",
                "product_id": "25009",
            },
            {
                "product_category": "Desserts",
                "product_name": "Ice Cream Scoop Single",
                "product_id": "236",
            },
            {
                "product_category": "Desserts",
                "product_name": "Lindt Chocolate Cheesecake",
                "product_id": "437",
            },
            {
                "product_category": "Desserts",
                "product_name": "LOTUS LAVA CAKE",
                "product_id": "25459",
            },
            {
                "product_category": "Desserts",
                "product_name": "MANGO CHEESE CAKE",
                "product_id": "25314",
            },
            {
                "product_category": "Desserts",
                "product_name": "MOLTEN FRENCH TOAST",
                "product_id": "25087",
            },
            {
                "product_category": "Desserts",
                "product_name": "Molten Lava Cake",
                "product_id": "170",
            },
            {
                "product_category": "Desserts",
                "product_name": "Nutella Dream Cake",
                "product_id": "10591",
            },
            {
                "product_category": "Desserts",
                "product_name": "Sizzling Skillet Brownie",
                "product_id": "431",
            },
            {
                "product_category": "Desserts",
                "product_name": "SNICKERS CAKE",
                "product_id": "25467",
            },
            {
                "product_category": "French Italian",
                "product_name": "Arcadian Special Medallions",
                "product_id": "50",
            },
            {
                "product_category": "French Italian",
                "product_name": "Arcadian Special Salad",
                "product_id": "10598",
            },
            {
                "product_category": "French Italian",
                "product_name": "ARGENTINIAN STEAK CHIMICHURRI",
                "product_id": "25464",
            },
            {
                "product_category": "French Italian",
                "product_name": "Asparagus Beef",
                "product_id": "10543",
            },
            {
                "product_category": "French Italian",
                "product_name": "Asparagus Chicken",
                "product_id": "409",
            },
            {
                "product_category": "French Italian",
                "product_name": "Baked Spaghetti with Shrimps",
                "product_id": "10565",
            },
            {
                "product_category": "French Italian",
                "product_name": "Beef Bearnaise",
                "product_id": "287",
            },
            {
                "product_category": "French Italian",
                "product_name": "Bordeaux Oven Roasted Chicken",
                "product_id": "10605",
            },
            {
                "product_category": "French Italian",
                "product_name": "Buttermilk Chicken Burger",
                "product_id": "25060",
            },
            {
                "product_category": "French Italian",
                "product_name": "Cajun Chicken with Salsa",
                "product_id": "412",
            },
            {
                "product_category": "French Italian",
                "product_name": "Ceaser Salad with Sundried Tomatoes",
                "product_id": "39",
            },
            {
                "product_category": "French Italian",
                "product_name": "Chardonnay Steak (BEEF)",
                "product_id": "441",
            },
            {
                "product_category": "French Italian",
                "product_name": "Chardonnay Steak (Chicken)",
                "product_id": "446",
            },
            {
                "product_category": "French Italian",
                "product_name": "Chargrilled Broccoli",
                "product_id": "25034",
            },
            {
                "product_category": "French Italian",
                "product_name": "Cheeseburger Sliders (Beef)",
                "product_id": "25040",
            },
            {
                "product_category": "French Italian",
                "product_name": "Chicken Parmesan Sliders",
                "product_id": "25039",
            },
            {
                "product_category": "French Italian",
                "product_name": "Chicken Schnitzel",
                "product_id": "10562",
            },
            {
                "product_category": "French Italian",
                "product_name": "Chili Cheese Breast",
                "product_id": "25062",
            },
            {
                "product_category": "French Italian",
                "product_name": "Cream of Chicken Soup",
                "product_id": "389",
            },
            {
                "product_category": "French Italian",
                "product_name": "Cream of Mushroom",
                "product_id": "10642",
            },
            {
                "product_category": "French Italian",
                "product_name": "Crispy Batter Fish",
                "product_id": "10564",
            },
            {
                "product_category": "French Italian",
                "product_name": "Crispy Fried Fish Burger",
                "product_id": "25038",
            },
            {
                "product_category": "French Italian",
                "product_name": "Extra Meat (Beef)",
                "product_id": "455",
            },
            {
                "product_category": "French Italian",
                "product_name": "Extra Meat (Chicken)",
                "product_id": "456",
            },
            {
                "product_category": "French Italian",
                "product_name": "Extra Meat (Seafood)",
                "product_id": "337",
            },
            {
                "product_category": "French Italian",
                "product_name": "Extra Sauce",
                "product_id": "10643",
            },
            {
                "product_category": "French Italian",
                "product_name": "Fiesta Deluxe Sandwich",
                "product_id": "25043",
            },
            {
                "product_category": "French Italian",
                "product_name": "Garden Green Salad with Grilled Chicken",
                "product_id": "42",
            },
            {
                "product_category": "French Italian",
                "product_name": "Grilled BBQ Burger",
                "product_id": "25059",
            },
            {
                "product_category": "French Italian",
                "product_name": "Grilled Jumbo Prawn with Lemon & Garlic Sauce",
                "product_id": "55",
            },
            {
                "product_category": "French Italian",
                "product_name": "Grilled Mutton Chops",
                "product_id": "25036",
            },
            {
                "product_category": "French Italian",
                "product_name": "Hoisin Chili Wings",
                "product_id": "25044",
            },
            {
                "product_category": "French Italian",
                "product_name": "Lasagne Beef",
                "product_id": "267",
            },
            {
                "product_category": "French Italian",
                "product_name": "Lasagne Chicken",
                "product_id": "179",
            },
            {
                "product_category": "French Italian",
                "product_name": "LOBSTER PER GRAM",
                "product_id": "25091",
            },
            {
                "product_category": "French Italian",
                "product_name": "Lobster Thermedor",
                "product_id": "56",
            },
            {
                "product_category": "French Italian",
                "product_name": "Mashed Potatoes",
                "product_id": "378",
            },
            {
                "product_category": "French Italian",
                "product_name": "Moroccan Chicken",
                "product_id": "338",
            },
            {
                "product_category": "French Italian",
                "product_name": "Mozambique Peri Chicken",
                "product_id": "10559",
            },
            {
                "product_category": "French Italian",
                "product_name": "Napolean Chicken",
                "product_id": "360",
            },
            {
                "product_category": "French Italian",
                "product_name": "Newport Grilled Fish",
                "product_id": "25033",
            },
            {
                "product_category": "French Italian",
                "product_name": "NORWEGIAN PINK SALMON",
                "product_id": "25462",
            },
            {
                "product_category": "French Italian",
                "product_name": "Pan Fried Fish",
                "product_id": "53",
            },
            {
                "product_category": "French Italian",
                "product_name": "Parmesan Chicken WITH RATTLESNAKE PASTA",
                "product_id": "225",
            },
            {
                "product_category": "French Italian",
                "product_name": "Parmesan Spaghetti",
                "product_id": "385",
            },
            {
                "product_category": "French Italian",
                "product_name": "Penne Ala Arrabiata Aux Poulet",
                "product_id": "183",
            },
            {
                "product_category": "French Italian",
                "product_name": "Penne Carbonara",
                "product_id": "290",
            },
            {
                "product_category": "French Italian",
                "product_name": "Philly Cheesesteak Sliders (Beef)",
                "product_id": "25042",
            },
            {
                "product_category": "French Italian",
                "product_name": "Philly Cheesesteak Sliders (Chicken)",
                "product_id": "25041",
            },
            {
                "product_category": "French Italian",
                "product_name": "Pollo Rosso",
                "product_id": "10606",
            },
            {
                "product_category": "French Italian",
                "product_name": "Popcorn Chicken Pasta",
                "product_id": "25019",
            },
            {
                "product_category": "French Italian",
                "product_name": "PORTO FLAME CHICKEN",
                "product_id": "25465",
            },
            {
                "product_category": "French Italian",
                "product_name": "Portobello Special Beef",
                "product_id": "10563",
            },
            {
                "product_category": "French Italian",
                "product_name": "Portobello Special Chicken",
                "product_id": "10542",
            },
            {
                "product_category": "French Italian",
                "product_name": "Poulet Aux Polo",
                "product_id": "46",
            },
            {
                "product_category": "French Italian",
                "product_name": "Poulet Grille",
                "product_id": "43",
            },
            {
                "product_category": "French Italian",
                "product_name": "Poulet Milano",
                "product_id": "268",
            },
            {
                "product_category": "French Italian",
                "product_name": "Primetime Burger (Beef)",
                "product_id": "25061",
            },
            {
                "product_category": "French Italian",
                "product_name": "Ribeye Steak \u2013 imported",
                "product_id": "47",
            },
            {
                "product_category": "French Italian",
                "product_name": "Seafood Chowder",
                "product_id": "35",
            },
            {
                "product_category": "French Italian",
                "product_name": "Seafood Delight",
                "product_id": "424",
            },
            {
                "product_category": "French Italian",
                "product_name": "Sicilian Chicken With Risotto Rice",
                "product_id": "408",
            },
            {
                "product_category": "French Italian",
                "product_name": "SOLE FISH WITH LEMON CAPERY SAUCE",
                "product_id": "25463",
            },
            {
                "product_category": "French Italian",
                "product_name": "Southern Chicken with Pineapple",
                "product_id": "10538",
            },
            {
                "product_category": "French Italian",
                "product_name": "Special Italiano Chicken",
                "product_id": "10539",
            },
            {
                "product_category": "French Italian",
                "product_name": "Special Italiano Pasta",
                "product_id": "182",
            },
            {
                "product_category": "French Italian",
                "product_name": "Spicy Fettuccini Chicken Pasta",
                "product_id": "289",
            },
            {
                "product_category": "French Italian",
                "product_name": "Stuffed Chicken Butter with Spicy Chili Sauce",
                "product_id": "269",
            },
            {
                "product_category": "French Italian",
                "product_name": "Stuffed Chicken Butter With White Sauce",
                "product_id": "349",
            },
            {
                "product_category": "French Italian",
                "product_name": "Stuffed Chicken Pasta",
                "product_id": "25037",
            },
            {
                "product_category": "French Italian",
                "product_name": "Stuffed Risotto Chicken",
                "product_id": "25035",
            },
            {
                "product_category": "French Italian",
                "product_name": "Toulon Fried Fish",
                "product_id": "10608",
            },
            {
                "product_category": "French Italian",
                "product_name": "Tucson Beef",
                "product_id": "286",
            },
            {
                "product_category": "Pizza",
                "product_name": "Chicken and Cheese Pizza",
                "product_id": "434",
            },
            {
                "product_category": "Pizza",
                "product_name": "Deep Stuffed Crust Pizza",
                "product_id": "10623",
            },
            {
                "product_category": "Pizza",
                "product_name": "Euro Fiesta Large",
                "product_id": "104",
            },
            {
                "product_category": "Pizza",
                "product_name": "Euro Fiesta Medium",
                "product_id": "103",
            },
            {
                "product_category": "Pizza",
                "product_name": "Euro Fiesta Small",
                "product_id": "102",
            },
            {
                "product_category": "Pizza",
                "product_name": "Feisty Chicken Tikka Large",
                "product_id": "95",
            },
            {
                "product_category": "Pizza",
                "product_name": "Feisty Chicken Tikka Medium",
                "product_id": "94",
            },
            {
                "product_category": "Pizza",
                "product_name": "Feisty Chicken Tikka Small",
                "product_id": "93",
            },
            {
                "product_category": "Pizza",
                "product_name": "Pepperoni Pizza Large",
                "product_id": "25054",
            },
            {
                "product_category": "Pizza",
                "product_name": "Pepperoni Pizza Medium",
                "product_id": "25053",
            },
            {
                "product_category": "Pizza",
                "product_name": "Pepperoni Pizza Small",
                "product_id": "25052",
            },
            {
                "product_category": "Pizza",
                "product_name": "Sizzling Chicken Fajita Large",
                "product_id": "98",
            },
            {
                "product_category": "Pizza",
                "product_name": "Sizzling Chicken Fajita Medium",
                "product_id": "97",
            },
            {
                "product_category": "Pizza",
                "product_name": "Sizzling Chicken Fajita Small",
                "product_id": "96",
            },
            {
                "product_category": "Pizza",
                "product_name": "Special Arcadian Pizza Large",
                "product_id": "110",
            },
            {
                "product_category": "Pizza",
                "product_name": "Special Arcadian Pizza Medium",
                "product_id": "109",
            },
            {
                "product_category": "Pizza",
                "product_name": "Special Arcadian Pizza Small",
                "product_id": "108",
            },
            {
                "product_category": "Pizza",
                "product_name": "Thai Shrimp Pizza",
                "product_id": "10581",
            },
            {
                "product_category": "Pizza",
                "product_name": "Thin Crust Pizza",
                "product_id": "111",
            },
            {
                "product_category": "PRIVE",
                "product_name": "ANGUS STRIPLOIN BEEF STEAK",
                "product_id": "25302",
            },
            {
                "product_category": "PRIVE",
                "product_name": "APPLE CIDER VINEGAR CHICKEN",
                "product_id": "25245",
            },
            {
                "product_category": "PRIVE",
                "product_name": "APPLE CRISP CHEESECAKE",
                "product_id": "25297",
            },
            {
                "product_category": "PRIVE",
                "product_name": "ARCADIAN SPECIAL AMERICAN CHOPSUEY",
                "product_id": "25301",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BAKED TUSCAN CHICKEN CASSEROLE",
                "product_id": "25240",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BANG BANG PASTA",
                "product_id": "25228",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BASIL GRILLED PRAWNS",
                "product_id": "25215",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BEEF TARO",
                "product_id": "25233",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BEEF WITH CHIMICHURRI SAUCE",
                "product_id": "25254",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BEIJING CHILLI CHICKEN",
                "product_id": "25259",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BEIJING CHILLI FISH",
                "product_id": "25278",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BEIJING CHILLI PRAWN",
                "product_id": "25279",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BIANCO BEEF",
                "product_id": "25241",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BURNT GARLIC PEPPER PRAWNS",
                "product_id": "25212",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BUTTERLY CHICKEN WITH GARLIC RICE",
                "product_id": "25294",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BUTTERLY FISH WITH GARLIC RICE",
                "product_id": "25295",
            },
            {
                "product_category": "PRIVE",
                "product_name": "BUTTERLY PRAWNS WITH GARLIC RICE",
                "product_id": "25296",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CAJUN CHICKEN",
                "product_id": "25247",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CANTONESE CHICKEN",
                "product_id": "25260",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CANTONESE FISH",
                "product_id": "25280",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CANTONESE PRAWN",
                "product_id": "25281",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CAPER SUN DRIED TOMATO PIZZA",
                "product_id": "25225",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CAPPUCCINO ROLLED BEEF",
                "product_id": "25235",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CARAMEL TOFFE CRUNCH",
                "product_id": "25298",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CHARCOAL BEEF SKEWERS",
                "product_id": "25209",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CHENS GARLIC PRAWNS",
                "product_id": "25256",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CHICKEN LETTUCE BALLS",
                "product_id": "25219",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CHICKEN PILLOWS WITH SWEET HEAVE SAUCE",
                "product_id": "25208",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CHICKEN STRIPS WITH CREAMY MOJO SAUCE",
                "product_id": "25206",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CHILLI AVACADO PRAWNS",
                "product_id": "25213",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CHILLI LEMONGRASS SPECIAL SOUP",
                "product_id": "25203",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CORRIENDER CHICKEN CHEESE BALLS",
                "product_id": "25307",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CRAZY CHICKEN SANDWICH",
                "product_id": "25242",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CRISPY CHILLI BEEF",
                "product_id": "25269",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CRISPY ORANGE BEEF",
                "product_id": "25268",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CROQUETTE CAESER SALAD",
                "product_id": "25224",
            },
            {
                "product_category": "PRIVE",
                "product_name": "CUBAN MOJO CHICKEN (FULL)",
                "product_id": "25251",
            },
            {
                "product_category": "PRIVE",
                "product_name": "DEEP FRIED BEEF",
                "product_id": "25236",
            },
            {
                "product_category": "PRIVE",
                "product_name": "DGENERAL TAOS CHICKEN",
                "product_id": "25258",
            },
            {
                "product_category": "PRIVE",
                "product_name": "DRAGONFIRE PRAWNS WITH CREAMY RISOTTO",
                "product_id": "25217",
            },
            {
                "product_category": "PRIVE",
                "product_name": "DRY SZECHUAN CHICKEN",
                "product_id": "25264",
            },
            {
                "product_category": "PRIVE",
                "product_name": "DRY SZECHUAN FISH",
                "product_id": "25288",
            },
            {
                "product_category": "PRIVE",
                "product_name": "DRY SZECHUAN PRAWN",
                "product_id": "25289",
            },
            {
                "product_category": "PRIVE",
                "product_name": "FAJITA PIZZA",
                "product_id": "25230",
            },
            {
                "product_category": "PRIVE",
                "product_name": "FETA CHEESE CHICKEN PIZZA",
                "product_id": "25231",
            },
            {
                "product_category": "PRIVE",
                "product_name": "GARDEN OF EDEN SALAD",
                "product_id": "25222",
            },
            {
                "product_category": "PRIVE",
                "product_name": "GARLIC PERMESAN CHICKEN",
                "product_id": "25253",
            },
            {
                "product_category": "PRIVE",
                "product_name": "GENERAL TAOS FISH",
                "product_id": "25276",
            },
            {
                "product_category": "PRIVE",
                "product_name": "GENERAL TAOS PRAWN",
                "product_id": "25277",
            },
            {
                "product_category": "PRIVE",
                "product_name": "GENERALTAOS CHICKEN",
                "product_id": "25305",
            },
            {
                "product_category": "PRIVE",
                "product_name": "GOLDEN FRIED PRAWNS",
                "product_id": "25214",
            },
            {
                "product_category": "PRIVE",
                "product_name": "GREEK FETA CHEESE SALAD",
                "product_id": "25221",
            },
            {
                "product_category": "PRIVE",
                "product_name": "HAKKA STYLE CHILI FISH",
                "product_id": "25453",
            },
            {
                "product_category": "PRIVE",
                "product_name": "HAKKA STYLE CHILI PRAWNS",
                "product_id": "25454",
            },
            {
                "product_category": "PRIVE",
                "product_name": "HAKKA STYLE CHILLI CHICKEN",
                "product_id": "25239",
            },
            {
                "product_category": "PRIVE",
                "product_name": "HAKKA STYLE CHILLI FISH",
                "product_id": "25272",
            },
            {
                "product_category": "PRIVE",
                "product_name": "HAKKA STYLE CHILLI PRAWN",
                "product_id": "25273",
            },
            {
                "product_category": "PRIVE",
                "product_name": "JAMBALAYA PRAWNS PASTA",
                "product_id": "25226",
            },
            {
                "product_category": "PRIVE",
                "product_name": "K MAC N CHEESE",
                "product_id": "25466",
            },
            {
                "product_category": "PRIVE",
                "product_name": "KARABI SWEET CHICKEN",
                "product_id": "25310",
            },
            {
                "product_category": "PRIVE",
                "product_name": "KING ORIENTAL LOBSTER WITH BURNT GARLIC RICE",
                "product_id": "25237",
            },
            {
                "product_category": "PRIVE",
                "product_name": "KOREAN CHICKEN CHEESE BALLS",
                "product_id": "25207",
            },
            {
                "product_category": "PRIVE",
                "product_name": "KOREAN CHICKEN WINGS",
                "product_id": "25306",
            },
            {
                "product_category": "PRIVE",
                "product_name": "KOREN PULLED BEEF IN CIABATTA BREAD",
                "product_id": "25250",
            },
            {
                "product_category": "PRIVE",
                "product_name": "KUNG PAO WINGS",
                "product_id": "25205",
            },
            {
                "product_category": "PRIVE",
                "product_name": "LEMON CORIANDER SOUP NEW",
                "product_id": "25200",
            },
            {
                "product_category": "PRIVE",
                "product_name": "MALA PEANUT CHICKEN",
                "product_id": "25265",
            },
            {
                "product_category": "PRIVE",
                "product_name": "MALA PEANUT FISH",
                "product_id": "25290",
            },
            {
                "product_category": "PRIVE",
                "product_name": "MALA PEANUT PRAWN",
                "product_id": "25291",
            },
            {
                "product_category": "PRIVE",
                "product_name": "MINT PESTO CHICKEN",
                "product_id": "25246",
            },
            {
                "product_category": "PRIVE",
                "product_name": "MUTTON SHANK WITH BROWN GRAVY",
                "product_id": "25238",
            },
            {
                "product_category": "PRIVE",
                "product_name": "Open Face Sandwich PRIVE",
                "product_id": "25313",
            },
            {
                "product_category": "PRIVE",
                "product_name": "OVEN BAKED CHICKEN IN PERI MOZAMBIQUE SAUCE",
                "product_id": "25249",
            },
            {
                "product_category": "PRIVE",
                "product_name": "PEPPERONI PIZZA",
                "product_id": "25232",
            },
            {
                "product_category": "PRIVE",
                "product_name": "PESTO PENNE PASTA",
                "product_id": "25229",
            },
            {
                "product_category": "PRIVE",
                "product_name": "PILLI PILLI PRAWNS",
                "product_id": "25210",
            },
            {
                "product_category": "PRIVE",
                "product_name": "PISTACHIO CRUSTED MUTTON CHOPS",
                "product_id": "25243",
            },
            {
                "product_category": "PRIVE",
                "product_name": "POLLO A LA BRASA",
                "product_id": "25248",
            },
            {
                "product_category": "PRIVE",
                "product_name": "PRAWNS DIMSUM",
                "product_id": "25218",
            },
            {
                "product_category": "PRIVE",
                "product_name": "QUINOA SALAD",
                "product_id": "25223",
            },
            {
                "product_category": "PRIVE",
                "product_name": "RASPBERRY BERET CHOCOLATE CAKE",
                "product_id": "25271",
            },
            {
                "product_category": "PRIVE",
                "product_name": "ROCCO CHICKEN",
                "product_id": "25261",
            },
            {
                "product_category": "PRIVE",
                "product_name": "ROCCO FISH",
                "product_id": "25282",
            },
            {
                "product_category": "PRIVE",
                "product_name": "ROCKET FISH",
                "product_id": "25311",
            },
            {
                "product_category": "PRIVE",
                "product_name": "SINGAPOREAN DRY CHILLI CHICKEN",
                "product_id": "25262",
            },
            {
                "product_category": "PRIVE",
                "product_name": "SINGAPOREAN DRY CHILLI FISH",
                "product_id": "25284",
            },
            {
                "product_category": "PRIVE",
                "product_name": "SINGAPOREAN DRY CHILLI PRAWN",
                "product_id": "25285",
            },
            {
                "product_category": "PRIVE",
                "product_name": "SOLE FISH FILLET WITH GINGER N COCOONUT CURRY",
                "product_id": "25252",
            },
            {
                "product_category": "PRIVE",
                "product_name": "SOYA BEEF WITH RICE",
                "product_id": "25234",
            },
            {
                "product_category": "PRIVE",
                "product_name": "SPICY NORMANDY SOLE",
                "product_id": "25263",
            },
            {
                "product_category": "PRIVE",
                "product_name": "STUFFED CHICKEN WITHCARAMELIZED ONIONS",
                "product_id": "25309",
            },
            {
                "product_category": "PRIVE",
                "product_name": "STUFFED FISH",
                "product_id": "25312",
            },
            {
                "product_category": "PRIVE",
                "product_name": "SWEET BASIL FIRE CHICKEN",
                "product_id": "25216",
            },
            {
                "product_category": "PRIVE",
                "product_name": "SZECHUAN RICE SOUP",
                "product_id": "25471",
            },
            {
                "product_category": "PRIVE",
                "product_name": "TAIWANESE POPCORN",
                "product_id": "25304",
            },
            {
                "product_category": "PRIVE",
                "product_name": "TAMARIND CORIANDER FISH",
                "product_id": "25266",
            },
            {
                "product_category": "PRIVE",
                "product_name": "TEMPURA PRAWNS",
                "product_id": "25220",
            },
            {
                "product_category": "PRIVE",
                "product_name": "THAI BEEF SALAD",
                "product_id": "25308",
            },
            {
                "product_category": "PRIVE",
                "product_name": "THAI CHICKEN IN CHILLI BEAN SAUCE",
                "product_id": "25267",
            },
            {
                "product_category": "PRIVE",
                "product_name": "THAI FISH IN CHILLI BEAN SAUCE",
                "product_id": "25292",
            },
            {
                "product_category": "PRIVE",
                "product_name": "THAI GINGER CHICKEN",
                "product_id": "25174",
            },
            {
                "product_category": "PRIVE",
                "product_name": "THAI GINGER FISH",
                "product_id": "25286",
            },
            {
                "product_category": "PRIVE",
                "product_name": "THAI GINGER PRAWNS",
                "product_id": "25449",
            },
            {
                "product_category": "PRIVE",
                "product_name": "THAI PRAWN IN CHILLI BEAN SAUCE",
                "product_id": "25293",
            },
            {
                "product_category": "PRIVE",
                "product_name": "TRADE",
                "product_id": "25198",
            },
            {
                "product_category": "PRIVE",
                "product_name": "TURIN STUFFED CHICKEN",
                "product_id": "25244",
            },
            {
                "product_category": "PRIVE",
                "product_name": "VEGETARIAN PASTA",
                "product_id": "25227",
            },
            {
                "product_category": "PRIVE",
                "product_name": "WALNUT WINGS",
                "product_id": "25204",
            },
            {
                "product_category": "PRIVE",
                "product_name": "WASABI CHILLI PRAWNS",
                "product_id": "25211",
            },
            {
                "product_category": "PRIVE",
                "product_name": "WOK CHARRED BEEF",
                "product_id": "25270",
            },
            {
                "product_category": "PRIVE",
                "product_name": "YANGS PEPPER GARLIC CHICKEN",
                "product_id": "25257",
            },
            {
                "product_category": "PRIVE",
                "product_name": "YANGS PEPPER GARLIC FISH",
                "product_id": "25442",
            },
            {
                "product_category": "PRIVE",
                "product_name": "YANGS PEPPER GARLIC PRAWNS",
                "product_id": "25472",
            },
            {
                "product_category": "PRIVE",
                "product_name": "YOUNGS PEPPER GARLIC FISH",
                "product_id": "25274",
            },
            {
                "product_category": "PRIVE",
                "product_name": "YOUNGS PEPPER GARLIC PRAWN",
                "product_id": "25275",
            },
            {
                "product_category": "Promotions",
                "product_name": "CHILD SEHRI BUFFET",
                "product_id": "25100",
            },
            {
                "product_category": "Promotions",
                "product_name": "CHOCOLATE OREO CARAMEL PIE 3 LBS",
                "product_id": "25085",
            },
            {
                "product_category": "Promotions",
                "product_name": "COMMITTEE LUNCH",
                "product_id": "25473",
            },
            {
                "product_category": "Promotions",
                "product_name": "DEAL A",
                "product_id": "25070",
            },
            {
                "product_category": "Promotions",
                "product_name": "DEAL B",
                "product_id": "25071",
            },
            {
                "product_category": "Promotions",
                "product_name": "DEAL C",
                "product_id": "25072",
            },
            {
                "product_category": "Promotions",
                "product_name": "Deep Fried Lasagne",
                "product_id": "25066",
            },
            {
                "product_category": "Promotions",
                "product_name": "Discounted Iftari",
                "product_id": "329",
            },
            {
                "product_category": "Promotions",
                "product_name": "Food Mob",
                "product_id": "328",
            },
            {
                "product_category": "Promotions",
                "product_name": "Food Mob Child",
                "product_id": "331",
            },
            {
                "product_category": "Promotions",
                "product_name": "HALF PORTION BEEF",
                "product_id": "25074",
            },
            {
                "product_category": "Promotions",
                "product_name": "HALF PORTION CHICKEN",
                "product_id": "25073",
            },
            {
                "product_category": "Promotions",
                "product_name": "HALF PORTION PRAWN",
                "product_id": "25075",
            },
            {
                "product_category": "Promotions",
                "product_name": "IFTAR BUFFET",
                "product_id": "25098",
            },
            {
                "product_category": "Promotions",
                "product_name": "IFTAR BUFFET CHILD",
                "product_id": "25097",
            },
            {
                "product_category": "Promotions",
                "product_name": "Iftar Econ Chinese Deal",
                "product_id": "25068",
            },
            {
                "product_category": "Promotions",
                "product_name": "Iftar Econ Continental Deal",
                "product_id": "25069",
            },
            {
                "product_category": "Promotions",
                "product_name": "KINGS FEAST BUFFET",
                "product_id": "315",
            },
            {
                "product_category": "Promotions",
                "product_name": "LINDT CHOCOLATE 3 LBS CAKE",
                "product_id": "25083",
            },
            {
                "product_category": "Promotions",
                "product_name": "Lions Share Platter",
                "product_id": "25067",
            },
            {
                "product_category": "Promotions",
                "product_name": "NUTELLA DREAM CAKE 3 LBS",
                "product_id": "25084",
            },
            {
                "product_category": "Promotions",
                "product_name": "SEHRI BUFFET",
                "product_id": "25099",
            },
            {
                "product_category": "Promotions",
                "product_name": "SEHRI BUFFET KIDS",
                "product_id": "25458",
            },
            {
                "product_category": "Test Category",
                "product_name": "PRA Test Item",
                "product_id": "374",
            },
            {
                "product_category": "Test Category",
                "product_name": "TEST ITEM",
                "product_id": "25088",
            },
            {
                "product_category": "testing",
                "product_name": "TSTING",
                "product_id": "25202",
            },
        ]

        products = []
        raya_branch = next((b for b in branches if b.name and "Raya" in b.name), None)

        for item in products_data:
            cat_name = item["product_category"]
            cat, _ = ProductCategory.objects.get_or_create(name=cat_name)

            price = Decimal(str(random.randint(100, 2000)))
            target_branch = raya_branch if cat_name.upper() == "PRIVE" else None

            product_code = (
                int(item["product_id"])
                if str(item["product_id"]).isdigit()
                else random.randint(10000, 99999)
            )

            product, created = Product.objects.get_or_create(
                product_code=product_code,
                defaults={
                    "name": item["product_name"],
                    "price": price,
                    "category": cat,
                    "branch": target_branch,
                },
            )
            if not created:
                needs_update = False
                if product.name != item["product_name"]:
                    product.name = item["product_name"]
                    needs_update = True
                if product.category != cat:
                    product.category = cat
                    needs_update = True
                if product.branch != target_branch:
                    product.branch = target_branch
                    needs_update = True
                if needs_update:
                    product.save(update_fields=["name", "category", "branch"])

            products.append(product)

        # Add Branch-Specific Menus
        special_menus = [
            ("Prive Menu", "Raya", "PRIVE-MENU-RAYA"),
        ]

        special_cat, _ = ProductCategory.objects.get_or_create(
            name="Special Menus (Branch Only)"
        )

        branch_map = {b.name: b for b in branches}
        start_code = 9000
        for menu_name, branch_name, _ in special_menus:
            br = branch_map.get(branch_name)
            if br:
                product, _ = Product.objects.get_or_create(
                    name=menu_name,
                    branch=br,
                    defaults={
                        "product_code": start_code,
                        "price": Decimal("1500.00"),
                        "category": special_cat,
                    },
                )
                start_code += 1
                products.append(product)

        return products
