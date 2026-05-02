import re


def parse_price(price):
    if price is None:
        return None

    price = str(price)
    price = price.replace("EGP", "").replace(",", "").strip()

    numbers = re.findall(r"\d+", price)
    if numbers:
        return int("".join(numbers))

    return None


def clean_prices(df):
    df["current_price"] = df["raw_current_price"].apply(parse_price)
    df["original_price"] = df["raw_original_price"].apply(parse_price)

    return df