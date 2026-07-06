import pandas as pd


def main() -> None:
    file = "Arcadian Gulberg Delivery Category Wise Sale 1NOV to 19 DEC.xls"
    df = pd.read_excel(file, engine="xlrd")

    for col in df.columns:
        print(col)
        print(df[col][1])

    print(len(df))
    print(df.iloc[0, 1])


if __name__ == "__main__":
    main()
