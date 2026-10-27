"""Run the ideal Snow City economy scenario (excludes driving and weather)."""
import json

from test_game import GameTests, ROOT


def main():
    GameTests.setUpClass()
    case = GameTests()
    try:
        case.setUp()
        try:
            case.game()
            result = case.page.evaluate((ROOT / 'tests/city_campaign.js').read_text())
            print(json.dumps(result, indent=2))
            if not result['completed']:
                raise AssertionError('City campaign did not complete')
        finally:
            case.tearDown()
    finally:
        GameTests.tearDownClass()


if __name__ == '__main__':
    main()
