"""
Copies images from the images/ folder into a structured test_outfits/ folder
organized by outfit name and clothing slot.
"""

import os
import shutil

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_outfits")

outfit_test_set = {
    "casual_outfit": {
        "style_name": "Clean Minimal / Everyday",
        "category": "Casual",
        "items": {
            "top": {
                "item_id": 15187,
                "product_type": "T-shirt",
                "color": "White",
                "pattern": "Solid",
            },
            "bottom": {
                "item_id": 39386,
                "product_type": "Jeans",
                "color": "Blue",
            },
            "shoes": {
                "item_id": 39988,
                "product_type": "Casual Shoes",
                "color": "White",
            },
            "accessory": {
                "item_id": 11188,
                "product_type": "Watch",
                "color": "Silver",
            },
        },
        "style_vibe": "clean, simple, versatile everyday casual (minimal palette with blue denim contrast)",
    },
    "sportswear_outfit": {
        "style_name": "Athletic / Performance Street",
        "category": "Sportswear",
        "items": {
            "top": {
                "item_id": 7964,
                "product_type": "T-shirt",
                "color": "Black",
                "pattern": "Graphic",
            },
            "layer": {
                "item_id": 15007,
                "product_type": "Jacket",
                "color": "Black",
                "pattern": "Solid",
            },
            "bottom": {
                "item_id": 17625,
                "product_type": "Track Pants",
                "color": "Black",
                "pattern": "Solid",
            },
            "shoes": {
                "item_id": 8913,
                "product_type": "Sports Shoes",
                "color": "White",
            },
            "accessory": {
                "item_id": 12735,
                "product_type": "Cap",
                "color": "Black",
                "gender": "Unisex",
            },
        },
        "style_vibe": "sporty monochrome with high contrast white sneakers (gym-to-street look)",
    },
    "formal_outfit": {
        "style_name": "Classic Business / Sharp",
        "category": "Formal",
        "items": {
            "top": {
                "item_id": 11119,
                "product_type": "Shirt",
                "color": "White",
                "pattern": "Solid",
            },
            "outerwear": {
                "item_id": 31742,
                "product_type": "Blazer",
                "color": "Black",
            },
            "bottom": {
                "item_id": 10257,
                "product_type": "Trousers",
                "color": "Black",
                "pattern": "Solid",
            },
            "shoes": {
                "item_id": 10633,
                "product_type": "Formal Shoes",
                "color": "Brown",
            },
            "accessories": [
                {
                    "item_id": 41250,
                    "product_type": "Belt",
                    "color": "Brown",
                },
                {
                    "item_id": 36768,
                    "product_type": "Watch",
                    "color": "Gold",
                },
            ],
        },
        "style_vibe": "classic formalwear with coordinated brown shoe+belt pairing and gold watch accent",
    },
}


def extract_items(items_dict):
    """Flatten the items dict into a list of (slot_name, item_id, product_type) tuples."""
    results = []
    for slot, value in items_dict.items():
        if isinstance(value, list):
            for i, item in enumerate(value):
                label = f"{slot}_{i+1}" if len(value) > 1 else slot
                results.append((label, item["item_id"], item["product_type"]))
        else:
            results.append((slot, value["item_id"], value["product_type"]))
    return results


def main():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    copied = 0
    missing = 0

    for outfit_name, outfit_data in outfit_test_set.items():
        outfit_dir = os.path.join(OUTPUT_DIR, outfit_name)
        os.makedirs(outfit_dir, exist_ok=True)

        print(f"\n{'='*50}")
        print(f"  {outfit_name}  —  {outfit_data['style_name']}")
        print(f"  Category: {outfit_data['category']}")
        print(f"{'='*50}")

        items = extract_items(outfit_data["items"])
        for slot, item_id, product_type in items:
            src = os.path.join(IMAGES_DIR, f"{item_id}.jpg")
            dst = os.path.join(outfit_dir, f"{slot}_{product_type.lower().replace(' ', '_')}_{item_id}.jpg")

            if os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"  ✓  {slot:<14}  {product_type:<16}  →  {os.path.basename(dst)}")
                copied += 1
            else:
                print(f"  ✗  {slot:<14}  {product_type:<16}  →  MISSING ({item_id}.jpg)")
                missing += 1

    print(f"\nDone — {copied} images copied, {missing} missing")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
