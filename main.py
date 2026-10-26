from src.game import SokobanKenneyGame

def main() -> SokobanKenneyGame:
    game = SokobanKenneyGame()
    return game


if __name__ == "__main__":
    game = main()
    game.run()
