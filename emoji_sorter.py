import random

def get_random_emoji():
    """
    Returns a single random emoji using Unicode ranges.
    Covers most emoji blocks in Unicode.
    """
    # Define emoji Unicode ranges
    emoji_ranges = [
        (0x1F600, 0x1F64F),  # Emoticons
        (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
        (0x1F680, 0x1F6FF),  # Transport and Map
        (0x1F1E0, 0x1F1FF),  # Regional indicators (flags)
        (0x2600, 0x26FF),    # Misc symbols
        (0x2700, 0x27BF),    # Dingbats
        (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
        (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
    ]
    
    # Pick a random range
    start, end = random.choice(emoji_ranges)
    
    # Generate random unicode point in that range
    unicode_point = random.randint(start, end)
    
    # Convert to emoji character
    return chr(unicode_point)

def get_random_emoji_safe():
    """
    Returns a random emoji from verified working ranges.
    More reliable but smaller selection.
    """
    # These ranges are known to contain valid emojis
    safe_ranges = [
        (0x1F600, 0x1F64F),  # Emoticons
        (0x1F680, 0x1F6C5),  # Transport and Map (partial)
        (0x1F910, 0x1F96B),  # Supplemental Symbols (partial)
        (0x2600, 0x2B55),    # Misc symbols (partial)
    ]
    
    start, end = random.choice(safe_ranges)
    unicode_point = random.randint(start, end)
    return chr(unicode_point)

# Example usage
if __name__ == "__main__":
    print("Random emoji:", get_random_emoji())
    print("Safe random emoji:", get_random_emoji_safe())
    
    # Generate 10 random emojis
    print("\n10 random emojis:")
    for i in range(10):
        print(get_random_emoji(), end=" ")
    print()