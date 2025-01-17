import os
from collections import defaultdict
from helpers.db import Measurement
from constants import GRAPH_IMAGE_PATH, ARMY
from helpers.spain_geography import CCAA_POPULATION, CCAA_ADMITTED_BEDS, CCAA_ICU_BEDS


def get_spain_vaccination_report(accumulated_doses_data, today_doses_data,
                                 accumulated_completed_vaccination_data, today_completed_vaccination_data):

    tweet = get_vaccination_sentence("Dosis", sum(accumulated_doses_data.values()),
                                      sum(today_doses_data.values())) + "\n"
    tweet += get_completed_vaccination_sentence("Pautas", sum(accumulated_completed_vaccination_data.values()),
                                                sum(today_completed_vaccination_data.values()))

    return tweet


def get_vaccination_report(accumulated_data, today_data, percentage):
    sentences = []
    sentence_generator = {
        True: get_completed_vaccination_sentence,
        False: get_vaccination_sentence
    }[percentage]

    for ccaa in accumulated_data:
        sentences.append(sentence_generator(ccaa, accumulated_data[ccaa], today_data[ccaa]))

    return sentences


def get_vaccination_sentence(territorial_unit, accumulated, today_total):
    return "- {0}: {1} 🔺{2}".format(territorial_unit, _format_number(accumulated),
                                     _format_number(today_total))


def get_completed_vaccination_sentence(territorial_unit, accumulated, today_total):
    population = CCAA_POPULATION[territorial_unit] if territorial_unit in CCAA_POPULATION \
        else sum(CCAA_POPULATION.values())
    percentage_population = accumulated / population * 100
    return "- {0}: {1} ({2}%) 🔺{3}".format(territorial_unit, _format_number(accumulated),
                                           _format_number(percentage_population),
                                           _format_number(today_total))


def get_report_by_ccaa(date_in_header, ccaas_today, ccaas_yesterday, ccaas_accumulated_today):
    tweets = []
    for ccaa in filter(lambda x: x != ARMY, sorted(ccaas_today.keys())):
        tweets.append(get_territorial_unit_report(ccaa, date_in_header, ccaas_today[ccaa],
                                                  ccaas_yesterday[ccaa], ccaas_accumulated_today[ccaa]))

    return tweets


def get_global_report(date_in_header, ccaas_today, ccaas_yesterday, ccaas_accumulated_today):
    global_today_data = get_global_data(ccaas_today)
    global_yesterday_data = get_global_data(ccaas_yesterday)
    global_accumulated_data = get_global_data(ccaas_accumulated_today)

    return get_territorial_unit_report("🇪🇸 España", date_in_header, global_today_data, global_yesterday_data,
                                       global_accumulated_data)


def get_global_data(dict_to_unpack):
    keys = set([key for ccaa in dict_to_unpack for key in dict_to_unpack[ccaa].keys()])
    ia_exists = Measurement.ACCUMULATED_INCIDENCE in keys
    keys.discard(Measurement.ACCUMULATED_INCIDENCE)

    result = defaultdict(lambda: 0)
    for key in keys:
        for ccaa in dict_to_unpack:
            result[key] += dict_to_unpack[ccaa][key] if dict_to_unpack[ccaa][key] else 0

    if ia_exists:
        result[Measurement.ACCUMULATED_INCIDENCE] = calculate_global_incidence(dict_to_unpack,
                                                                               Measurement.ACCUMULATED_INCIDENCE)
        result[Measurement.PERCENTAGE_ADMITTED] = calculate_global_incidence(dict_to_unpack,
                                                                             Measurement.PERCENTAGE_ADMITTED)
        result[Measurement.PERCENTAGE_ICU] = calculate_global_incidence(dict_to_unpack,
                                                                        Measurement.PERCENTAGE_ICU)

    return result


def calculate_global_incidence(dict_to_unpack, measurement):

    population_to_compare = {
        Measurement.ACCUMULATED_INCIDENCE.value: CCAA_POPULATION,
        Measurement.PERCENTAGE_ADMITTED.value: CCAA_ADMITTED_BEDS,
        Measurement.PERCENTAGE_ICU.value: CCAA_ICU_BEDS
    }[measurement.value]

    total_cases = 0
    population = 0
    ccaas = filter(lambda x: x != ARMY, dict_to_unpack.keys())
    for ccaa in ccaas:
        total_cases += dict_to_unpack[ccaa][measurement] * population_to_compare[ccaa] / 100000
        population += population_to_compare[ccaa]

    return total_cases / population * 100000 if population else 0


def get_territorial_unit_report(territorial_unit, header_date, today_data, yesterday_data, accumulated_today):

    sentences = list()
    sentences.append(f"{territorial_unit} - {header_date}:")
    sentences.append("")
    sentences.append(get_report_sentence("🧪 PCRs", today_data.get(Measurement.PCRS),
                                         yesterday_data.get(Measurement.PCRS),
                                         accumulated_today.get(Measurement.PCRS)))

    if Measurement.PCRS_LAST_24H in today_data:
        sentences.append(get_report_sentence("🧪 PCRs 24h", today_data.get(Measurement.PCRS_LAST_24H),
                                             yesterday_data.get(Measurement.PCRS_LAST_24H)))

    sentences.append(get_report_sentence_with_unit("💥 IA",
                                                   today_data.get(Measurement.ACCUMULATED_INCIDENCE),
                                                   yesterday_data.get(Measurement.ACCUMULATED_INCIDENCE),
                                                   "/100.000 hab."))
    sentences.append("")
    sentences.append(get_report_sentence("😢 Muertes", today_data.get(Measurement.DEATHS),
                                         yesterday_data.get(Measurement.DEATHS),
                                         accumulated_today.get(Measurement.DEATHS)))
    sentences.append("")

    # PCRs last 24 hour is not present in Weekly info.
    # Vaccines info cannot be shown in daily reports because info. is not updated at the same time.
    if Measurement.PCRS_LAST_24H not in today_data:
        sentences.append(get_report_sentence("💉 Dosis", today_data.get(Measurement.VACCINATIONS),
                                             yesterday_data.get(Measurement.VACCINATIONS),
                                             accumulated_today.get(Measurement.VACCINATIONS)))
        sentences.append(get_report_sentence("💉 Pautas", today_data.get(Measurement.COMPLETED_VACCINATIONS),
                                             yesterday_data.get(Measurement.COMPLETED_VACCINATIONS),
                                             accumulated_today.get(Measurement.COMPLETED_VACCINATIONS)))
    else:
        sentences.append(
            get_report_sentence_with_unit("🚑 Hospitalizados", today_data.get(Measurement.PERCENTAGE_ADMITTED),
                                          yesterday_data.get(Measurement.PERCENTAGE_ADMITTED), "%"))
        sentences.append(get_report_sentence_with_unit("🏥 UCI", today_data.get(Measurement.PERCENTAGE_ICU),
                                                       yesterday_data.get(Measurement.PERCENTAGE_ICU), "%"))

    return "\n".join(sentences)


def get_report_sentence_with_unit(stat, today_total, yesterday_total, units):
    formatted_number = _format_number(today_total)
    return "{0}: {1}{2} {3}".format(stat, formatted_number, units, get_tendency_emoji(today_total, yesterday_total))


def get_report_sentence(stat, today_total, yesterday_total, accumulated=None):
    total_sentence = "(Tot.: {0:,})".format(accumulated).replace(",", ".") if accumulated else ""
    sentence = "{0}: {1} {2} {3}".format(stat, "{0:+,}".format(today_total).replace(",", "."),
                                         get_tendency_emoji(today_total, yesterday_total),
                                         total_sentence).strip()

    return " ".join(sentence.split())


def get_tendency_emoji(today_number, yesterday_number):

    if yesterday_number is None:
        result = ""
    elif today_number > yesterday_number:
        result = f'🔺{_format_number(today_number - yesterday_number)}'
    elif yesterday_number > today_number:
        result = f'🔻{_format_number(yesterday_number - today_number)}'
    else:
        result = '🔙'

    return result


def get_graph_url(start=None, end=None, additional_vars=None, graph_path=GRAPH_IMAGE_PATH):
    vars_str = "&" + "&".join([f"var-{k}={v}" for k, v in additional_vars.items()]) if additional_vars else ""
    start_str = f"&from={int(start.strftime('%s')) * 1000}" if start else ""
    end_str = f"&to={int(end.strftime('%s')) * 1000}" if end else ""
    grafana_server = os.environ.get("GRAFANA_SERVER", "http://localhost:3000")

    return os.path.join(grafana_server, graph_path) + start_str + end_str + vars_str


def _format_number(number):
    return "{0:,}".format(round(number, 2)).replace(",", "#").replace(".", ",").replace("#", ".")
