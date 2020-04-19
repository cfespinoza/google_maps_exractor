import logging
import threading
import time

from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from gmaps.commons.commons import validate_required_keys
from gmaps.commons.extractor.extractor import AbstractGMapsExtractor
from selenium.webdriver.support import expected_conditions as ec

from gmaps.places.writer import PlaceDbWriter, PlaceFileWriter


class PlacesExtractor(AbstractGMapsExtractor):
    """Clase que implementa gmaps.commons.extractor.extractor.AbstractGMapsExtractor con las particularidades necesarias
    para obtener la información de los locales comerciales.

    ...
    Attributes
    ----------
    logger
        referencia a una instancia de logging.Logger para esta clase
    _place_name
        nombre del local comercial que se extraerá la información
    _url
        url del local comercial del que vamos a extraer información
    _num_reviews
        número de comentarios/reviews que se quiere extraer para este local comercial
    _INDEX_TO_DAY
        atributo de ayuda para traducir de número a día de la semana debido al formato en el que lo hace la plataforma
        de google maps
    _coords_xpath_selector
        consulta de xpath para obtener las coordenadas del local comercial
    _telephone_xpath_selector
        consulta de xpath para obtener el teléfono del local comercial
    _openning_hours_xpath_selector
        consulta de xpath para obtener el horario de apertura del local comercial
    _back_button_xpath
        consulta de xpath para obtener el botón de `ir a atrás` durante la navegación en la página del local comercial
    _all_reviews_back_button_xpath
        consulta de xpath para obtener el botón de `ir a atrás` de la vista de comentarios
    _occupancy_by_hours_xpath
        consulta de xpath para obtener la ocupación por horas del local comercial
    _place_name_xpath
        consulta de xpath para obtener el nombre del local comercial
    _place_score_xpath
        consulta de xpath para obtener la puntuación del local comercial
    _occupancy_container_elements_xpath_query
        consulta de xpath para obtener el elemento padre del elemento que contiene la ocupación por horas del local
        comercial
    _total_votes_xpath
        consulta de xpath para obtener el número total de votos del local comercial
    _address_xpath
        consulta de xpath para obtener la dirección del local comercial
    _see_all_reviews_button
        consulta de xpath para obtener el botón de `ver todas los comentarios` del local comercial
    _price_range
        consulta de xpath para obtener el rango del precio del local comercial
    _premise_type
        consulta de xpath para obtener el tipo del local comercial
    _style
        consulta de xpath para obtener el estilo del local comercial
    _review_css_class
        consulta de xpath para obtener los elementos de reviews
    _thread_local
        nombre del thread local (en desuso)
    _thread_driver_id
        nombre del driver id asociado al thread (en desuso)
    _postal_code
        código postal al que pertenece el local
    _extraction_date
        fecha de extraccion en la que se está ejecutando el programa
    _output_config
        configuración del soporte de salida para la ejecución
    _places_types
        tipo de locales que se buscan en la ejecución

    Methods
    -------
    boot_writer()
        arranca y configura el writer que corresponda dependiendo del soporte de salida que se haya configurado para la
        ejecución del programa.
    _boot_writer()
        función que arrancaba y configuraba el writer de este extractor leyendo de la configuración del soporte de
        salida configurada para la ejecución. Actualmente en desuso.
    set_driver(driver)
        función que registra el driver asociado a este extractor en el thread de ejecución. Actualmente en desuso.
    auto_boot()
        función de arranque e inicialización de driver y writer
    _get_day_from_index(idx)
        función auxiliar que permite obtener el nombre del día pasándole el índice que tienen google maps.
    _get_occupancy(external_driver)
        función que obtiene la ocupación por día
    _get_place_info(provided_driver)
        función que extrae la información general del local comercial
    _get_comments(place_name, sleep_time, external_driver)
        función que extrae los comentarios para el local comercial
    _scrap(provided_driver)
        función auxiliar que contiene la lógica de realizar el scrapping en caso de que la url de de búsqueda nos
        redirija a una página de resultados en lugar de la página del local comercial.
    scrap(provided_driver)
        función principal encargada de la extracción de la información, para ello primero checkea si el local que se va
        a procesar ya está registrado en el soporte de salida para lo que usa la instancia de `writer`. De no estar ya
        procesado se accede a la url del local comercial, en caso de que sea ambigua y gmaps redireccione a un listado
        de locales comerciales, se hace la llamada a la función _scrap. Una vez obtenida la información, se hace la
        llamada a writer.export_data(data) que se encarga de persisitir los datos obtenidos en el soporte de salida
        correspondiente que se haya configurado para la ejecución.
    """

    def __init__(self, driver_location=None, url=None, place_name=None, num_reviews=None, output_config=None,
                 postal_code=None, places_types=None, extraction_date=None):
        """Constructor de la clase

        Parameters
        ----------
        driver_location: str
            ubicación del chromedriver
        url : str
            url del local comercial
        place_name : str
            nombre del local comercial
        num_reviews : int
            número de comentarios que se quiere extraer
        output_config : dict
            configuración del soporte de salida
        postal_code : str
            código postal al que pertenece el local comercial
        places_types : list
            lista de tipos de local comercial. Establecido en la configuración de la ejecución del programa
        extraction_date : str
            fecha de ejecución del programa
        """
        super().__init__(driver_location, output_config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._place_name = place_name
        self._url = url
        self._num_reviews = num_reviews
        self._INDEX_TO_DAY = {
            "0": "domingo",
            "*0": "domingo",
            "1": "lunes",
            "*1": "lunes",
            "2": "martes",
            "*2": "martes",
            "3": "miercoles",
            "*3": "miercoles",
            "4": "jueves",
            "*4": "jueves",
            "5": "viernes",
            "*5": "viernes",
            "6": "sabado",
            "*6": "sabado"
        }
        self._coords_xpath_selector = "//*[@id='pane']/div/div[1]/div/div/div[@data-section-id='ol']/div/div[@class='section-info-line']/span[@class='section-info-text']/span[@class='widget-pane-link']"
        self._telephone_xpath_selector = "//*[@id='pane']/div/div[1]/div/div/div[@data-section-id='pn0']/div/div[@class='section-info-line']/span/span[@class='widget-pane-link']"
        self._openning_hours_xpath_selector = "//*[@id='pane']/div/div[1]/div/div/div[@jsaction='pane.info.dropdown;keydown:pane.info.dropdown;focus:pane.focusTooltip;blur:pane.blurTooltip;']/div[3]"
        self._back_button_xpath = "//*[@id='pane']/div/div/div[@class='widget-pane-content-holder']/div/button"
        self._all_reviews_back_button_xpath = "//*[@id='pane']/div/div[@tabindex='-1']//button[@jsaction='pane.topappbar.back;focus:pane.focusTooltip;blur:pane.blurTooltip']"
        self._occupancy_by_hours_xpath = "div[contains(@class, 'section-popular-times-graph')]/div[contains(@class, 'section-popular-times-bar')]"
        self._place_name_xpath = "//*[@id='pane']/div/div[@tabindex='-1']/div/div//h1"
        self._place_score_xpath = "//*[@id='pane']/div/div[@tabindex='-1']//span[@class='section-star-display']"
        self._occupancy_container_elements_xpath_query = "//div[contains(@class, 'section-popular-times-container')]/div"
        self._total_votes_xpath = "//*[@id='pane']/div/div[@tabindex='-1']/div/div/div[@class='section-hero-header-title']//span[@class='section-rating-term-list']//button"
        self._address_xpath = "//*[@id='pane']/div/div[@tabindex='-1']/div/div/div[@data-section-id='ad']//span[@class='widget-pane-link']"
        self._see_all_reviews_button = "//*[@id='pane']/div/div[1]/div/div/div/div/div[@jsaction='pane.reviewlist.goToReviews']/button"
        self._price_range = "//*[@id='pane']/div/div[1]/div/div/div[2]/div[1]/div[2]/div/div[1]/span[2]/span/span[2]/span[2]/span[1]/span[@role='text']"
        self._premise_type = "//*[@id='pane']/div/div[1]//button[@jsaction='pane.rating.category']"
        self._style = "//*[@id='pane']/div/div[1]/div/div/jsl/button/div//div[@class='section-editorial-attributes-summary']"
        self._review_css_class = "section-review-review-content"
        self._thread_local = threading.local()
        self._thread_driver_id = "{classname}_{place}_driver".format(classname=self.__class__.__name__,
                                                                     place=self._place_name)
        self._postal_code = postal_code
        self._extraction_date = extraction_date
        self._output_config = output_config
        self._places_types = "+".join(places_types)
        self.auto_boot()

    def boot_writer(self):
        """Arranca y configura el writer que corresponda dependiendo del soporte de salida que se haya configurado para
        la ejecución del programa.
        """
        if self._output_config.get("type") == "file":
            # soporte de salida: `output_config.type="file"`
            config = self._output_config.get("file")
            required_keys = ["results_path"]
            if validate_required_keys(required_keys, config):
                self._writer = PlaceFileWriter(config=config)
                self._writer.auto_boot()
            else:
                self.logger.error("wrong writer config. required configuration is not present")
                self.logger.error("make sure the output_config has the required configuration set: {required}"
                                  .format(required=required_keys))
        elif self._output_config.get("type") == "db":
            # soporte de salida: `output_config.type="db"`
            config = self._output_config.get("db").get("config")
            required_keys = ["host", "database", "db_user", "db_pass"]
            if validate_required_keys(required_keys, config):
                self._writer = PlaceDbWriter(config=config)
                self._writer.auto_boot()
            else:
                self.logger.error("wrong writer config. required configuration is not present")
                self.logger.error("make sure the output_config has the required configuration set: {required}"
                                  .format(required=required_keys))
        elif self._output_config:
            # en caso de no haber establecido el `output_config.type` pero sí se ha definido en `output_config` la
            # configuración de conexión a la base de datos
            required_keys = ["host", "database", "db_user", "db_pass"]
            if validate_required_keys(required_keys, self._output_config):
                self._writer = PlaceDbWriter(config=self._output_config)
                self._writer.auto_boot()
            else:
                self.logger.error("wrong writer config. required configuration is not present")
                self.logger.error("make sure the output_config has the required configuration set: {required}"
                                  .format(required=required_keys))
        else:
            self.logger.error("writer type is not supported")

    def _boot_writer(self):
        """Función que arrancaba y configuraba el writer de este extractor leyendo de la configuración del soporte de
        salida configurada para la ejecución. Actualmente en desuso.
        """
        if self._output_config:
            self._writer = PlaceDbWriter(self._output_config)

    def set_driver(self, driver):
        """Función que registra el driver asociado a este extractor en el thread de ejecución. Actualmente en desuso."""
        self._driver = driver
        setattr(self._thread_local, self._thread_driver_id, self._driver)

    def auto_boot(self):
        """Función de arranque e inicialización de driver y writer."""
        self.logger.debug("overwrite 'auto_boot' function")
        super().auto_boot()
        self.logger.debug("booting writer")
        self.boot_writer()
        self.logger.debug("writer booted")

    def _get_day_from_index(self, idx):
        """Función auxiliar que permite obtener el nombre del día pasándole el índice que tienen google maps.

        Arguments
        ---------
        idx : int
            índice del día

        Returns
        -------
        str
            devuelve el nombre del día por índice, en caso de no encontrarlo devuelve `unknown`
        """
        return self._INDEX_TO_DAY.get(idx, "unknown")

    def _get_occupancy(self, external_driver=None):
        """Función que obtiene la ocupación por día.

        Arguments
        ---------
        external_driver : webdriver.Chrome
            se le pasa por argumento el driver a usar para la extracción de la ocupación

        Returns
        -------
        dict
            se devuelve un diccionario con la ocupación por día, teniendo como clave el día
        """
        driver = external_driver if external_driver else self.get_driver()
        occupancy = None
        occupancy_obj = {}
        try:
            occupancy = driver.find_element_by_class_name('section-popular-times')
            if occupancy:
                days_occupancy_container = occupancy.find_elements_by_xpath(
                    self._occupancy_container_elements_xpath_query)
                for d in days_occupancy_container:
                    day = self._get_day_from_index(d.get_attribute("jsinstance"))
                    occupancy_by_hour = d.find_elements_by_xpath(self._occupancy_by_hours_xpath)
                    occupancy_by_hour_values = [o.get_attribute("aria-label") for o in occupancy_by_hour]
                    occupancy_obj[day] = occupancy_by_hour_values
        except NoSuchElementException:
            self.logger.warning("there is no occupancy elements for -{name}-: {url}".format(name=self._place_name,
                                                                                            url=self._url))
        return occupancy_obj

    def _get_place_info(self, provided_driver=None):
        """Función que extrae la información general del local comercial. Así también se llama a las funciones para
        obtener la ocupación y los comentarios

        Arguments
        ---------
        provided_driver : webdriver.Chrome
            driver que se usará para extraer la información del local comercial

        Returns
        -------
        dict
            devuelve la información completa del local comercial en un diccionario de python

        """
        driver = provided_driver if provided_driver else self.get_driver()
        # extract basic info
        name_obj = self.get_obj_text(xpath_query=self._place_name_xpath, external_driver=driver)
        name_val = name_obj if name_obj else self._place_name
        score_obj = self.get_obj_text(xpath_query=self._place_score_xpath, external_driver=driver)
        total_score_obj = self.get_obj_text(xpath_query=self._total_votes_xpath, external_driver=driver)
        total_score_val = total_score_obj.replace("(", "").replace(")", "") if total_score_obj else total_score_obj
        address_obj = self.get_obj_text(xpath_query=self._address_xpath, external_driver=driver)
        coords_obj = self.get_obj_text(xpath_query=self._coords_xpath_selector, external_driver=driver)
        telephone_obj = self.get_obj_text(xpath_query=self._telephone_xpath_selector, external_driver=driver)
        opening_obj = self.get_info_obj(xpath_query=self._openning_hours_xpath_selector, external_driver=driver)
        price_range = self.get_obj_text(xpath_query=self._price_range, external_driver=driver)
        style = self.get_obj_text(xpath_query=self._style, external_driver=driver)
        premise_type = self.get_obj_text(xpath_query=self._premise_type, external_driver=driver)
        opening_value = opening_obj.get_attribute("aria-label").split(",") if opening_obj else []
        occupancy_obj = self._get_occupancy(external_driver=driver)
        comments_list = self._get_comments(self._place_name, self.sleep_m, external_driver=driver)
        place_info = {
            "name": name_val,
            "score": score_obj,
            "total_scores": total_score_val,
            "address": address_obj,
            "occupancy": occupancy_obj,
            "coordinates": coords_obj,
            "telephone_number": telephone_obj,
            "opening_hours": opening_value,
            "comments": comments_list,
            "zip_code": self._postal_code,
            "date": self._extraction_date,
            "execution_places_types": self._places_types,
            "price_range": price_range,
            "style": style,
            "premise_type": premise_type,
            "extractor_url": self._url
        }
        self.logger.info("info retrieved for place -{name}-".format(name=self._place_name))
        return place_info

    def _get_comments(self, place_name=None, sleep_time=None, external_driver=None):
        """Función que extrae los comentarios para el local comercial.

        Arguments
        ---------
        place_name : str
            nombre del local comercial
        sleep_time : int
            tiempo de espera para que el driver renderice los elementos de la web
        external_driver : webdriver.Chrome
            driver que se usará para hacer la extracción de los comentarios en caso de ser provisto, en caso contrario
            se usará el asociado a la instancia de la clase

        Returns
        -------
        list
            lista de comentarios encontrados para el local comercial
        """
        # get all reviews button
        driver = external_driver if external_driver else self.get_driver()
        self.logger.info("trying to retrieve comments for place -{place}-".format(place=place_name))
        button_see_all_reviews = self.get_info_obj(self._see_all_reviews_button)
        reviews_elements_list = driver.find_elements_by_class_name(self._review_css_class)
        if len(reviews_elements_list) < self._num_reviews and button_see_all_reviews:
            self.logger.info("all reviews button has been found")
            # change page to next comments and iterate
            driver.execute_script("arguments[0].click();", button_see_all_reviews)
            driver.wait.until(ec.url_changes(driver.current_url))
            self.force_sleep(sleep_time)
            aux_reviews = driver.find_elements_by_class_name(self._review_css_class)
            have_finished = False
            while not have_finished:
                # iterates appending comments until it reaches the `self._num_reviews` or the found comments don't
                # change between iterations
                previous_iteration_found = len(aux_reviews)
                last_review = aux_reviews[-1]
                driver.execute_script("arguments[0].scrollIntoView(true);", last_review)
                self.force_sleep(sleep_time)
                aux_reviews = driver.find_elements_by_class_name(self._review_css_class)
                have_finished = previous_iteration_found == len(aux_reviews) or len(aux_reviews) >= self._num_reviews
            # At this point the last `self._num_reviews` reviews must be shown
            self.logger.info("retrieving comment bucle has finished")

        # extract content of each element
        reviews_elements_list = driver.find_elements_by_class_name(self._review_css_class)
        comments = [elem.text for elem in reviews_elements_list]
        self.logger.info("found -{total_reviews}- comments for restaurant -{place_name}-".format(
            total_reviews=len(comments), place_name=place_name))
        return comments

    def _scrap(self, provided_driver=None):
        """Función auxiliar que contiene la lógica de realizar el scrapping en caso de que la url de de búsqueda nos
        redirija a una página de resultados en lugar de la página del local comercial.

        Arguments
        ---------
        provided_driver : webdriver.Chrome
            driver sobre el que se usará para realizar la extracción. En caso de no estar definido se usará el de que
            tenga definida la clase

        Returns
        -------
        dict
            devuelve el contenido de la información extraída en un diccionario python
        """
        driver = provided_driver if provided_driver else self.get_driver()
        # inicialización de la información que ya se conoce del local comercial
        place_info = {
            "name": self._place_name,
            "zip_code": self._postal_code,
            "date": self._extraction_date,
            "extractor_url": self._url
        }
        try:
            self.force_sleep(self.sleep_xs)
            # búsqueda del local comercial en el listado de resultados: `self.shared_result_elements_xpath_query`
            page_elements = driver.find_elements_by_xpath(self.shared_result_elements_xpath_query)
            places_objs = {place.text.split("\n")[0]: place for place in page_elements}
            if self._place_name in places_objs.keys():
                # el nombre del local comercial se encuentra en los resultados y se procede a clickar sobre él y extraer
                # la información una vez se haya cargado la página del local comercial
                self.logger.info("place found in search list due to ambiguous name nearby")
                found_place = places_objs.get(self._place_name)
                driver.execute_script("arguments[0].click();", found_place)
                driver.wait.until(ec.url_changes(driver.current_url))
                self.force_sleep(self.sleep_m)
                place_info = self._get_place_info(provided_driver=driver)
            else:
                self.logger.warning("place was not found in search list. There is something wrong with: {name}".format(
                    name=self._place_name))
        except StaleElementReferenceException as sere:
            # se ha detectado un error tratando de acceder a algún elemento del DOM de la página y se vuelve a intentar
            # extraer la información sin volver a procesar ninguna URL. Llamada recursiva a _scrap
            self.logger.error(str(sere))
            self.logger.warning("problems accessing to -{place}- reviews from ambiguous results: -{url}-".format(
                place=self._place_name, url=driver.current_url))
            self.logger.warning("trying to look up reviews again")
            place_info = self._scrap(driver)
        except TimeoutException as te:
            # se ha detectado de timeout esprando a que la página termine de cargar y se vuelve a intentar a
            # extraer la información sin volver a procesar ninguna URL. Llamada recursiva a _scrap
            self.logger.error(str(te))
            self.logger.warning("problems accessing to -{place}- reviews from ambiguous results: -{url}-".format(
                place=self._place_name, url=driver.current_url))
            self.logger.warning("trying to look up reviews again")
            place_info = self._scrap(driver)
        except Exception as e:
            # error no controlado durante la extracción de la información. Se sale de la ejecución sin forzar la
            # extracción de la información
            self.logger.error(str(e))
            self.logger.warning("problems accessing to -{place}- reviews from ambiguous results: -{url}-".format(
                place=self._place_name, url=driver.current_url))
        finally:
            return place_info

    def scrap(self, provided_driver=None):
        """Función principal encargada de la extracción de la información, para ello primero checkea si el local que se
        va a procesar ya está registrado en el soporte de salida para lo que usa la instancia de `writer`. De no estar
        ya procesado se accede a la url del local comercial, en caso de que sea ambigua y Google Maps redireccione a un
        listado de locales comerciales, se hace la llamada a la función _scrap. Una vez obtenida la información, se hace
        la llamada a `writer.export_data(data)` que se encarga de persisitir los datos obtenidos en el soporte de salida
        correspondiente que se haya configurado para la ejecución.

        Arguments
        ---------
        provided_driver : webdriver.Chrome
            driver que se usará para realizar la extracción, en caso de no estar definido, se usará el que se haya
            definido para la instancia de la clase

        Returns
        -------
        True
            en caso de que se exporte correctamente los datos
        False
            en caso de que algo hubiera ocurrido durante la extracción o la exportación
        dict
            en caso de que no se haya writer definido
        """
        logging.info("scrap process for place -{name}- with url -{url}- is starting".format(
            name=self._place_name, url=self._url))
        driver = provided_driver if provided_driver else self.get_driver()
        init_time = time.time()
        place_info = None
        result_to_return = None
        try:
            # checkeo si ya existe registro para la fecha de extracción y el nombre del local para evitar volver a
            # procesarlo
            is_registered = self._writer.is_registered(self._place_name, self._extraction_date)
            if is_registered:
                self.logger.warning("the place: -{name}- for date: -{date}- is already processed".format(
                    name=self._place_name, date=self._extraction_date))
                result_to_return = True
            else:
                driver.get(self._url)
                driver.wait.until(ec.url_changes(self._url))
                self.force_sleep(self.sleep_m)
                place_info = self._get_place_info(provided_driver=driver)
                result_to_return = self.export_data(place_info)
        except TimeoutException as te:
            # en caso de un error de debido a la demora en la carga de la página web, se registra en los logs el error y
            # se vuelve a intentar la extracción llamando a la función  `_scrap`
            self.logger.warning("{exception} - timeout exception waiting for place -{place}- in url: -{url}-".format(
                place=self._place_name,
                url=self._url,
                exception=str(te)
            ))
            self.logger.warning("forcing to look up information again")
            place_info = self._scrap(provided_driver=driver)
            result_to_return = self.export_data(place_info)
        except StaleElementReferenceException as sere:
            # en caso de un error de debido a inconsistencia en el DOM de la página web, se registra en los logs el
            # error y se vuelve a intentar la extracción llamando a la función  `_scrap`
            self.logger.warning(
                "{exception} - stale element reference detected during reviews extraction: -{name}- and -{url}-".format(
                    exception=str(sere),
                    name=self._place_name,
                    url=self._url
                ))
            self.force_sleep(self.sleep_m)
            self.logger.warning("forcing to look up information again")
            place_info = self._scrap(provided_driver=driver)
            result_to_return = self.export_data(place_info)
        except Exception as e:
            self.logger.error("error during reviews extraction for -{name}-: {error}".format(name=self._place_name,
                                                                                             error=str(e)))
        finally:
            self.finish()

        end_time = time.time()
        elapsed = int(end_time - init_time)
        self.logger.info("process the place -{name}- has took: -{elapsed}- seconds".format(name=self._place_name,
                                                                                           elapsed=elapsed))
        logging.info("scrap process for place -{name}- with url -{url}- is finishing".format(
            name=self._place_name, url=self._url))
        return result_to_return
