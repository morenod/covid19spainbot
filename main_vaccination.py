import logging
from datetime import datetime, timedelta
from urllib.error import HTTPError
from helpers.twitter import Twitter
from helpers.db import Influx, Measurement
from helpers.ministry_report import VaccinesMinistryReport
from main_daily import update_stat
from helpers.reports import get_vaccination_report, get_spain_vaccination_report, get_graph_url
from constants import VACCINE_IMAGE_PATH

twitter = Twitter()
influx = Influx()


def main():

    today = datetime.now()

    data = influx.get_stat_group_by_day(Measurement.VACCINATIONS, today)

    if not data:
        try:
            update_vaccinations(today)
            publish_report(today)
        except HTTPError:
            logging.info("PDF is not available yet...")
        except Exception as e:
            logging.exception("Unhandled exception while trying to publish tweets")
            dm_text = f"There was an unhandled exception. Trace:\n\n{str(e)}"[0:280]
            twitter.send_dm(dm_text)


def update_vaccinations(today):
    vaccination_report = VaccinesMinistryReport(today, 3)
    accumulated_vaccinations = vaccination_report.get_column_data(4, num_rows=20)
    accumulated_completed_vaccinations = vaccination_report.get_column_data(7, num_rows=20)
    update_stat(Measurement.VACCINATIONS, accumulated_vaccinations, today)
    update_stat(Measurement.COMPLETED_VACCINATIONS, accumulated_completed_vaccinations, today)


def publish_report(today):
    today_vaccinations = influx.get_stat_group_by_day(Measurement.VACCINATIONS, today)
    today_completed_vaccinations = influx.get_stat_group_by_day(Measurement.COMPLETED_VACCINATIONS, today)
    accumulated_vaccinations = influx.get_stat_accumulated_until_day(Measurement.VACCINATIONS, today)
    accumulated_completed_vaccinations = influx.get_stat_accumulated_until_day(Measurement.COMPLETED_VACCINATIONS,
                                                                               today)

    today_str = today.strftime("%d/%m/%Y")
    spain_tweet = get_spain_vaccination_report(accumulated_vaccinations, today_vaccinations,
                                               accumulated_completed_vaccinations, today_completed_vaccinations)
    interactive_graph_sentence = "➡️ Gráfico Interactivo: https://home.aitormagan.es/d/TeEplNgRk/covid-vacunas-espana?orgId=1"
    spain_tweet = f"🇪🇸 España - Estado vacunación a {today_str}:\n\n{spain_tweet}\n\n{interactive_graph_sentence}"
    graph_url = get_graph_url(datetime(2021, 1, 1), today, graph_path=VACCINE_IMAGE_PATH)
    last_tweet = twitter.publish_tweet_with_media(spain_tweet, graph_url)

    army_string = "Fuerzas Armadas"
    today_vaccinations.pop(army_string)
    today_completed_vaccinations.pop(army_string)
    accumulated_vaccinations.pop(army_string)
    accumulated_completed_vaccinations.pop(army_string)

    sentences_vaccination = get_vaccination_report(accumulated_vaccinations, today_vaccinations, False)
    last_tweet = twitter.publish_sentences_in_tweets(sentences_vaccination, f"💉 Total Dosis a {today_str}",
                                                    last_tweet=last_tweet)

    sentences_completed_vaccination = get_vaccination_report(accumulated_completed_vaccinations,
                                                             today_completed_vaccinations, True)
    twitter.publish_sentences_in_tweets(sentences_completed_vaccination, f"💉 Total Pautas Completas a {today_str}",
                                       last_tweet=last_tweet)


if __name__ == "__main__":
    main()
