import random
NUMBERS = list(range(37))  # 0..36
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def spin():
    return random.choice(NUMBERS)

def is_red(number: int) -> bool:
    return number in RED_NUMBERS