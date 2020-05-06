import json
import unittest
from datetime import datetime

from gmaps.executions.reader import ExecutionDbReader

from gmaps.places.extractor import PlacesExtractor
from gmaps.places.writer import PlaceDbWriter
from gmaps.results.optimized_extractor import OptimizedResultsExtractor
from selenium.webdriver.support import expected_conditions as ec


class TestGmapsScrapper(unittest.TestCase):
    _driver_location = "/home/cflores/cflores_workspace/gmaps-extractor/resources/chromedriver"
    _base_url = "https://www.google.com/maps/place/28047+Madrid/@40.3911256,-3.763457,14z"
    _postal_code = "28047"
    _places_types = ["Restaurante", "Bar"]
    _output_config = {
        "host": "localhost",
        "database": "gmaps",
        "db_user": "postgres",
        "db_pass": "1234"
    }
    _place = {
        "name": "Restaurante Costa Verde",
        "address": "Calle Vía Carpetana, 322",
        "url": "https://www.google.com/maps/search/28047+Madrid+Restaurante+Bar+Restaurante+Costa+Verde/@40.3911256,-3.763457,14z"
    }

    def test_scrap_zip_code(self):
        num_pages = 1
        scraper = OptimizedResultsExtractor(driver_location=self._driver_location,
                                            postal_code=self._postal_code,
                                            places_types=self._places_types,
                                            num_pages=num_pages,
                                            base_url=self._base_url)
        results = scraper.scrap()
        print(json.dumps(results))
        assert len(results) != 0
        assert all([result.get("name") and result.get("url") and result.get("address") for result in results])

    def test_scrap_single_place_in_db(self):
        place = {
            "name": "Restaurante Costa Verde",
            "address": "Calle Vía Carpetana, 322",
            "url": "https://www.google.com/maps/search/28047+Madrid+Restaurante+Bar+Restaurante+Costa+Verde/@40.3911256,-3.763457,14z"
        }

        extraction_date = datetime.now().isoformat()
        scraper = PlacesExtractor(driver_location=self._driver_location,
                                  url=place.get("url"),
                                  place_name=place.get("name"),
                                  place_address=place.get("address"),
                                  num_reviews=3,
                                  output_config=self._output_config,
                                  postal_code=self._postal_code,
                                  places_types=self._places_types,
                                  extraction_date=extraction_date)
        results = scraper.scrap()
        print(results)
        assert len(results.keys()) > 0

    def test_scrap_single_place_no_db(self):
        place = {
            "name": "Cafetería Cobar",
            "address": "",
            "url": "https://www.google.com/maps/search/28053+Madrid+Bar+Restaurante+Cafeteria+Cafeter%C3%ADa+Cobar/@40.376347,-3.6869967,14z"
        }

        extraction_date = datetime.now().isoformat()
        scraper = PlacesExtractor(driver_location=self._driver_location,
                                  url=place.get("url"),
                                  place_name=place.get("name"),
                                  place_address=place.get("address"),
                                  num_reviews=3,
                                  output_config=None,
                                  postal_code=self._postal_code,
                                  places_types=self._places_types,
                                  extraction_date=extraction_date)
        results = scraper.scrap()
        print(json.dumps(results))
        assert len(results.keys()) > 0

    def test_db_writer_is_regitered(self):
        # place = {
        #     "name": "La Andaluza Vía Carpetana - Madrid",
        #     "address": "Calle Vía Carpetana, 330, 28047 Madrid",
        #     "date": datetime.now().isoformat()
        # }
        place = {
            "name": "Restaurante Costa Verde",
            "address": "Calle Vía Carpetana, 322",
            "date": datetime.now().isoformat()
        }
        print(json.dumps(place))
        writer = PlaceDbWriter(self._output_config)
        is_registered = writer.is_registered(place)
        assert is_registered is True

    def test_extract_place_info_openning_hours(self):
        extraction_date = datetime.now().isoformat()
        scraper = PlacesExtractor(driver_location=self._driver_location,
                                  url=self._place.get("url"),
                                  place_name=self._place.get("name"),
                                  place_address=self._place.get("address"),
                                  num_reviews=3,
                                  output_config=self._output_config,
                                  postal_code=self._postal_code,
                                  places_types=self._places_types,
                                  extraction_date=extraction_date)
        scraper._driver.get(self._place.get("url"))
        scraper._driver.wait.until(ec.url_changes(self._place.get("url")))
        results = scraper._get_place_info()
        scraper.finish()
        print(json.dumps(results))
        assert len(results.keys()) > 0
        assert len(results.get("opening_hours")) == 7

    def get_recovered_executions(self, date):
        reader = ExecutionDbReader(self._output_config)
        reader.auto_boot()
        # executions = reader.recover_execution(date="2020-05-05")
        executions = reader.recover_execution(date=date.isoformat())
        reader.finish()
        return executions

    def test_recover_execution(self):
        date = datetime(2020, 5, 5)
        executions = self.get_recovered_executions(date)
        print(json.dumps(executions))
        assert all(["commercial_premise_id" in execution
                    and "commercial_premise_name" in execution
                    and "commercial_premise_url" in execution for execution in executions])


if __name__ == '__main__':
    unittest.main()
