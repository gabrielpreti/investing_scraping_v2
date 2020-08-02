import logging
import json
import os
import boto3
import urllib3
import re
import datetime
import unicodedata
from lxml import html
import time

BASE_URL = "https://br.investing.com/equities"
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'

LOGGING_LEVEL = logging.getLevelName(os.environ['LOGGING_LEVEL'])
LOGGER = logging.getLogger()
LOGGER.setLevel(LOGGING_LEVEL)

s3_client = boto3.resource("s3")
s3_bucket = s3_client.Bucket(os.environ['CRAWLING_OUTPUT_BUCKET_NAME'])

http_connection_pool = urllib3.PoolManager()


def lambda_handler(event, context):
    LOGGER.debug("Received event: %s", event)
    LOGGER.debug("Received context: %s", context)
    now = datetime.datetime.now()

    records = event['Records']
    for record in records:
        stock_code = json.loads(record['body'])['stock_code']
        LOGGER.debug("Crawling stock %s", stock_code)

        crawled_stock_data = get_stock_info_json(http_connection_pool, stock_code)
        key = '%s/%s.json' % (now.strftime('%Y-%m-%d'), stock_code)
        LOGGER.debug("Putting %s to key %s", crawled_stock_data, key)
        s3_bucket.put_object(Body=crawled_stock_data, Key=key, StorageClass="STANDARD_IA")
        LOGGER.info("Stored object %s in s3", key)
        time.sleep(10)  # this is for us not be banned from our destiny


#######################################################################################################################
#######################################################################################################################
def get_stock_info_dict(connection_pool, stock):
    stock_info = {}
    infos = {'General-Information': parse_stock_general_information,
             'General-Profile': parse_stock_general_profile,
             'Finance-Finance': parse_stock_finance_finance,
             'Finance-Demonstrations': finance_demonstrations,
             'Finance-Balances': finance_balances,
             'Finance-CashFlow': finance_cash_flow,
             'Finance-Indicators': finance_indicators,
             'Finance-Profits': finance_profits,
             'Technical-TechnicalAnalysis': technical_technical_analysis,
             'Technical-CandlestickPattern': technical_candlestick_pattern,
             'Technical-ConsensualEstimates': consensual_estimates}
    for k in infos.keys():
        info = __get_info(k, infos[k], connection_pool, stock)
        stock_info[info[0]] = info[1]

    stock_info['datetime'] = str(datetime.datetime.now())
    return stock_info


def get_stock_info_json(connection_pool, stock):
    return json.dumps(get_stock_info_dict(connection_pool, stock))


#######################################################################################################################
#######################################################################################################################
def set_dict_key_value(d, key, value):
    key = key.replace('.', '').strip()
    value = value.strip() if isinstance(value, str) else value
    d[key] = value

    return value


def normalize_and_encode(str_value):
    return unicodedata.normalize('NFKD', str_value).encode('ascii', 'ignore')


def generate_html_tree(connection_pool, url, http_method='GET', headers={'User-Agent': USER_AGENT}, fields=None):
    req = connection_pool.request(method=http_method, url=url, headers=headers, fields=fields)

    if req.status != 200:
        LOGGER.error("HTTP code %s for url %s", req.status, url)
    else:
        LOGGER.debug("HTTP code %s for url %s", req.status, url)

    return html.fromstring(normalize_and_encode(req.data.decode('utf-8')))


# ###Geral/Informacao
def parse_stock_general_information(connection_pool, stock):
    general_information_data = {}

    html_tree = generate_html_tree(connection_pool=connection_pool, url="%s/%s" % (BASE_URL, stock))
    data = html_tree.xpath('//div[@class="instrumentHead"]/h1[@itemprop="name"]')[0].text_content()
    stock_code = re.search("\((.*)\)", data).group(1)
    set_dict_key_value(general_information_data, 'code', stock_code)
    LOGGER.debug("%s=%s" % ("code", stock_code))

    data = html_tree.xpath(
        '//div[@class="clear overviewDataTable overviewDataTableWithTooltip"]//div[@class="inlineblock"] | //div[@class="first inlineblock"]')
    for div in data:
        set_dict_key_value(general_information_data, div.getchildren()[0].text_content(),
                           div.getchildren()[1].text_content())

    return general_information_data


# ###Geral/Perfil
def parse_stock_general_profile(connection_pool, stock):
    general_profile_data = {}

    html_tree = generate_html_tree(connection_pool=connection_pool, url="%s/%s-company-profile" % (BASE_URL, stock))
    data = html_tree.xpath('//div[@class="companyProfileHeader"]/div')
    for div in data:
        prop = div.text
        value = div.text_content().replace(prop, '')
        set_dict_key_value(general_profile_data, prop, value)
        LOGGER.debug("%s=%s" % (prop, value))

    return general_profile_data


# ###Financas/Financas
def parse_stock_finance_finance(connection_pool, stock):
    finance_finance_data = {}
    html_tree = generate_html_tree(connection_pool=connection_pool, url="%s/%s-financial-summary" % (BASE_URL, stock))
    summaries = html_tree.xpath('//div[@id="rsdiv"]/div[@class="companySummaryIncomeStatement"]')
    for summary in summaries:
        title = summary.xpath('h3/a')[0].text_content()
        title_dict = set_dict_key_value(finance_finance_data, title, {})
        LOGGER.debug(title)

        data = summary.xpath('div[@class="info float_lang_base_2"]/div[@class="infoLine"]')
        for div in data:
            spans = div.getchildren()
            item, value, complement = (
                spans[0].text_content(), spans[2].text_content().strip(), spans[1].text_content().strip())
            LOGGER.debug("\t%s=%s\t%s" % (item, value, complement))
            set_dict_key_value(title_dict, item, (value, complement))

        data = summary.xpath('table[@class="genTbl openTbl companyFinancialSummaryTbl"]/thead//th')
        encerramentos_exercicios = [d.text_content().strip() for d in data[1:]]
        data = summary.xpath('table[@class="genTbl openTbl companyFinancialSummaryTbl"]/tbody/tr')
        for tr in data:
            trchildrens = tr.getchildren()
            item = trchildrens[0].text_content()
            item_dict = set_dict_key_value(title_dict, item, {})
            LOGGER.debug('\t' + item)
            for e, v in zip(encerramentos_exercicios, tr.getchildren()[1:]):
                set_dict_key_value(item_dict, e, v.text_content())
                LOGGER.debug("\t\t%s=%s" % (e, v.text_content().strip()))
    return finance_finance_data


# ###Financas/Demonstracoes
def finance_demonstrations(connection_pool, stock):
    finance_demonstrations_data = {}
    html_tree = generate_html_tree(connection_pool=connection_pool, url='%s/%s-income-statement' % (BASE_URL, stock))
    data = html_tree.xpath('//div[@id="rrtable"]/table//tr[@id="header_row"]/th')
    encerramentos_exercicios = ["%s/%s" % (children[1].text_content().strip(), children[0].text_content().strip()) for
                                children in data[1:]]
    data = html_tree.xpath('//div[@id="rrtable"]/table//td/span[@class=" bold"]/../..')
    for item in data:
        item_name = item.getchildren()[0].text_content()
        itemname_dict = set_dict_key_value(finance_demonstrations_data, item_name, {})
        LOGGER.debug(item_name)
        for e, v in zip(encerramentos_exercicios, item.getchildren()[1:]):
            set_dict_key_value(itemname_dict, e, v.text_content())
            LOGGER.debug("\tExercicio=%s:\t%s" % (e, v.text_content()))
    return finance_demonstrations_data


# ###Financas/Balanco Patrimonial
def finance_balances(connection_pool, stock):
    finance_balances_data = {}

    html_tree = generate_html_tree(connection_pool=connection_pool, url='%s/%s-balance-sheet' % (BASE_URL, stock))
    data = html_tree.xpath('//div[@id="rrtable"]/table//tr[@id="header_row"]/th')
    encerramentos_exercicios = ["%s/%s" % (children[1].text_content().strip(), children[0].text_content().strip()) for
                                children in data[1:]]
    data = html_tree.xpath('//div[@id="rrtable"]/table//td/span[@class=" bold"]/../..')
    for item in data:
        item_name = item.getchildren()[0].text_content()
        itemname_dict = set_dict_key_value(finance_balances_data, item_name, {})
        LOGGER.debug(item_name)
        for e, v in zip(encerramentos_exercicios, item.getchildren()[1:]):
            set_dict_key_value(itemname_dict, e, v.text_content())
            LOGGER.debug("\tExercicio=%s:\t%s" % (e, v.text_content()))
    return finance_balances_data


# ###Financas/Fluxo de Caixa
def finance_cash_flow(connection_pool, stock):
    finance_cashflow_data = {}
    html_tree = generate_html_tree(connection_pool=connection_pool, url='%s/%s-cash-flow' % (BASE_URL, stock))
    data = html_tree.xpath('//div[@id="rrtable"]/table//tr[@id="header_row"]/th')
    encerramentos_exercicios = ["%s/%s" % (children[1].text_content().strip(), children[0].text_content().strip()) for
                                children in data[1:]]
    data = html_tree.xpath('//div[@id="rrtable"]/table//td/span[@class=" bold"]/../..')
    for item in data:
        item_name = item.getchildren()[0].text_content()
        itemname_dict = set_dict_key_value(finance_cashflow_data, item_name, {})
        LOGGER.debug(item_name)
        for e, v in zip(encerramentos_exercicios, item.getchildren()[1:]):
            set_dict_key_value(itemname_dict, e, v.text_content())
            LOGGER.debug("\tExercicio=%s:\t%s" % (e, v.text_content()))
    return finance_cashflow_data


# ###Financas/Indicadores
def finance_indicators(connection_pool, stock):
    finance_indicators_data = {}
    html_tree = generate_html_tree(connection_pool=connection_pool, url='%s/%s-ratios' % (BASE_URL, stock))
    escopo_indicadores = [x.text_content().strip() for x in html_tree.xpath('//table[@id="rrTable"]/thead/tr/th')[1:]]
    indicadores = html_tree.xpath('//table[@id="rrTable"]/tbody/tr[@id="childTr"]/td/div/table/tbody/tr/td/span/../..')
    for indicador in indicadores:
        indicator_name = indicador.getchildren()[0].text_content()
        indicatorname_dict = set_dict_key_value(finance_indicators_data, indicator_name, {})
        LOGGER.debug(indicator_name)
        for e, i in zip(escopo_indicadores, indicador.getchildren()[1:]):
            set_dict_key_value(indicatorname_dict, e, i.text_content())
            LOGGER.debug("\t%s=%s" % (e, i.text_content()))
    return finance_indicators_data


# ###Financas/Lucros
def finance_profits(connection_pool, stock):
    finance_profits_data = {}
    html_tree = generate_html_tree(connection_pool=connection_pool, url='%s/%s-earnings' % (BASE_URL, stock))
    columns = [col.text_content().replace("/", "").strip() for col in
               html_tree.xpath(
                   '//table[@class="genTbl openTbl ecoCalTbl earnings earningsPageTbl"]/thead/tr/th[text()]')]
    earningshistory = html_tree.xpath('//tr[@name="instrumentEarningsHistory"]')
    for history in earningshistory:
        exercise_date = history.getchildren()[1].text_content()
        exercisedate_dict = set_dict_key_value(finance_profits_data, exercise_date, {})
        LOGGER.debug("Exercicio=" + exercise_date)
        for c, h in zip(columns, history.getchildren()):
            value = h.text_content().replace("/", "").strip() if h.text_content().startswith(
                "/") else h.text_content().strip()
            set_dict_key_value(exercisedate_dict, c, value)
            LOGGER.debug("\t%s=%s" % (c, value))
    return finance_profits_data


# ###Tecnica/Analise Tecnica
def technical_technical_analysis(connection_pool, stock):
    technical_analysis_data = {}
    html_tree = generate_html_tree(connection_pool=connection_pool, url='%s/%s-technical' % (BASE_URL, stock))
    periods = [(p.text_content(), p.get('pairid'), p.get('data-period')) for p in
               html_tree.xpath('//div[@id="technicalstudiesSubTabs"]/ul/li')]
    for period in periods:
        period_name = period[0]
        periodname_dict = set_dict_key_value(technical_analysis_data, period_name, {})
        LOGGER.debug(period_name)
        html_tree = generate_html_tree(connection_pool=connection_pool, http_method='POST',
                                       url='https://br.investing.com/instruments/Service/GetTechincalData',
                                       headers={'User-Agent': USER_AGENT, 'X-Requested-With': 'XMLHttpRequest'},
                                       fields={'pairID': period[1], 'period': period[2]})

        tech_summary_div = html_tree.xpath('//div[@id="techStudiesInnerWrap"]')[0]

        summary = tech_summary_div.xpath('//div[@class="summary"]/span[1]')[0].text_content()
        periodname_resumo_dict = set_dict_key_value(periodname_dict, 'Resumo', {})
        set_dict_key_value(periodname_resumo_dict, 'Resumo', summary)
        LOGGER.debug('\tResumo=%s' % (summary))

        for summary_table_line in tech_summary_div.xpath('div[@class="summaryTableLine"]'):
            name, value = (summary_table_line[0].text_content().replace(':', ''), summary_table_line[1].text_content())
            periodname_resumo_name_dict = set_dict_key_value(periodname_resumo_dict, name, {})

            set_dict_key_value(periodname_resumo_name_dict, 'Resumo', value)
            LOGGER.debug("\t\t%s=%s" % (name, value))

            moving_avg_summ = summary_table_line[2].getchildren()
            x, y = (
                moving_avg_summ[0].text_content(), moving_avg_summ[1].text_content().replace('(', '').replace(')', ''))
            set_dict_key_value(periodname_resumo_name_dict, x, y)
            LOGGER.debug("\t\t\t%s=%s" % (x, y))

            tech_indicators_sum = summary_table_line[3].getchildren()
            x, y = (tech_indicators_sum[0].text_content(),
                    tech_indicators_sum[1].text_content().replace('(', '').replace(')', ''))
            set_dict_key_value(periodname_resumo_name_dict, x, y)
            LOGGER.debug("\t\t\t%s=%s" % (x, y))

        periodname_pontospivot_dict = set_dict_key_value(periodname_dict, 'Pontos de Pivot', {})
        LOGGER.debug("\tPontos de Pivot")
        pivot_points_table = html_tree.xpath('//table[@id="curr_table"]')[0]
        headers = [x.text_content().strip() for x in pivot_points_table.xpath('thead/tr/th')[1:]]
        pivot_indicators = pivot_points_table.xpath('tbody/tr')
        for indicator in pivot_indicators:
            indicator_name = indicator.getchildren()[0].text_content()
            periodname_pontospivot_indicatorname_dict = set_dict_key_value(periodname_pontospivot_dict, indicator_name,
                                                                           {})
            LOGGER.debug("\t\t%s" % (indicator_name))
            for h, i in zip(headers, indicator.getchildren()[1:]):
                set_dict_key_value(periodname_pontospivot_indicatorname_dict, h, i.text_content())
                LOGGER.debug("\t\t\t%s=%s" % (h, i.text_content()))

        periodname_indicadorestecnicos_dict = set_dict_key_value(periodname_dict, 'Indicadores Tecnicos', {})
        LOGGER.debug("\tIndicadores Tecnicos")
        tech_indicators_table = html_tree.xpath('//table[@id="curr_table"]')[1]
        headers = [x.text_content().strip() for x in tech_indicators_table.xpath('thead/tr/th')[1:]]
        tech_indicators = tech_indicators_table.xpath('tbody/tr')
        for indicator in tech_indicators[:-1]:
            indicator_name = indicator.getchildren()[0].text_content()
            periodname_indicadorestecnicos_indicatorname_dict = set_dict_key_value(periodname_indicadorestecnicos_dict,
                                                                                   indicator_name, {})
            LOGGER.debug("\t\t%s" % (indicator_name))
            for h, i in zip(headers, indicator.getchildren()[1:]):
                set_dict_key_value(periodname_indicadorestecnicos_indicatorname_dict, h, i.text_content())
                LOGGER.debug("\t\t\t%s=%s" % (h, i.text_content().strip()))
        periodname_indicadorestecnicos_total_dict = set_dict_key_value(periodname_indicadorestecnicos_dict, 'Total', {})
        LOGGER.debug("\t\tTotal")
        for p in tech_indicators_table.xpath('tbody/tr[last()]/td/p')[:-1]:
            p_children = p.getchildren()
            x, y = p_children[0].text_content().strip().replace(':', ''), p_children[1].text_content()
            set_dict_key_value(periodname_indicadorestecnicos_total_dict, x, y)
            LOGGER.debug("\t\t\t%s=%s" % (x, y))
        x = tech_indicators_table.xpath('tbody/tr[last()]/td/p[last()]/span')[0].text_content()
        set_dict_key_value(periodname_indicadorestecnicos_total_dict, 'Resumo', x)
        LOGGER.debug("\t\t\tResumo=%s" % (x))

        periodname_mediasmoveis_dict = set_dict_key_value(periodname_dict, 'Medias Moveis', {})
        LOGGER.debug("\tMedias Moveis")
        moving_avg_table = html_tree.xpath('//table[@id="curr_table"]')[2]
        headers = [x.text_content().strip() for x in moving_avg_table.xpath('thead/tr/th')[1:]]
        moving_avgs = moving_avg_table.xpath('tbody/tr')
        for mavg in moving_avgs[:-1]:
            mavgname = mavg.getchildren()[0].text_content()
            periodname_mediasmoveis_mavgname_dict = set_dict_key_value(periodname_mediasmoveis_dict, mavgname, {})
            LOGGER.debug("\t\t%s" % (mavgname))
            for h, v in zip(headers, mavg.getchildren()[1:]):
                periodname_mediasmoveis_mavgname_h_dict = set_dict_key_value(periodname_mediasmoveis_mavgname_dict, h,
                                                                             {})
                LOGGER.debug("\t\t\t%s" % (h))

                value = v.xpath('span/..')[0].text
                set_dict_key_value(periodname_mediasmoveis_mavgname_h_dict, 'Valor', value)
                LOGGER.debug("\t\t\t\tValor=%s" % (value))

                action = v.xpath('span')[0].text.strip()
                set_dict_key_value(periodname_mediasmoveis_mavgname_h_dict, 'Acao', action)
                LOGGER.debug("\t\t\t\tAcao=%s" % (action))
        periodname_mediasmoveis_total_dict = set_dict_key_value(periodname_mediasmoveis_dict, 'Total', {})
        LOGGER.debug("\t\tTotal")
        for p in moving_avg_table.xpath('tbody/tr[last()]/td/p')[:-1]:
            p_children = p.getchildren()
            x, y = (p_children[0].text_content().strip().replace(':', ''), p_children[1].text_content())
            set_dict_key_value(periodname_mediasmoveis_total_dict, x, y)
            LOGGER.debug("\t\t\t%s=%s" % (x, y))
        y = tech_indicators_table.xpath('tbody/tr[last()]/td/p[last()]/span')[0].text_content().strip()
        set_dict_key_value(periodname_mediasmoveis_total_dict, 'Resumo', y)
        LOGGER.debug("\t\t\tResumo=%s" % (y))

    return technical_analysis_data


# ###Tecnica/Padrao de Candlestick
def technical_candlestick_pattern(connection_pool, stock):
    tecnical_candlestick_pattern_data = {}
    candlestickpatterns_dict = set_dict_key_value(tecnical_candlestick_pattern_data, 'Candlestick Patterns', {})
    html_tree = generate_html_tree(connection_pool=connection_pool, url='%s/%s-candlestick' % (BASE_URL, stock))
    candlestick_patterns_table = \
        html_tree.xpath('//table[@class="genTbl closedTbl ecoCalTbl patternTable js-csp-table"]')[
            0]
    headers = [x.text_content().strip() for x in candlestick_patterns_table.xpath('thead/tr/th')]
    patterns = candlestick_patterns_table.xpath('tbody/tr[@id]')
    for p in patterns:
        values = p.getchildren()
        name = values[1].text_content()
        candlesticpatterns_name_dict = set_dict_key_value(candlestickpatterns_dict, name, {})
        LOGGER.debug(name)

        x, y = headers[0], values[0].get('title')
        set_dict_key_value(candlesticpatterns_name_dict, x, y)
        LOGGER.debug("\t%s=%s" % (x, y))

        x, y = headers[1], values[2].text_content()
        set_dict_key_value(candlesticpatterns_name_dict, x, y)
        LOGGER.debug("\t%s=%s" % (x, y))

        x, y = headers[2], values[3].get('title')
        set_dict_key_value(candlesticpatterns_name_dict, x, y)
        LOGGER.debug("\t%s=%s" % (x, y))

        x, y = headers[3], values[4].text_content()
        set_dict_key_value(candlesticpatterns_name_dict, x, y)
        LOGGER.debug("\t%s=%s" % (x, y))

        x, y = headers[4], values[5].text_content() if len(values) == 6 else ""
        set_dict_key_value(candlesticpatterns_name_dict, x, y)
        LOGGER.debug("\t%s=%s" % (x, y))
    return tecnical_candlestick_pattern_data


# ###Tecnica/Estimativas Consensuais
def consensual_estimates(connection_pool, stock):
    consensual_estimates_data = {}
    html_tree = generate_html_tree(connection_pool=connection_pool, url='%s/%s-consensus-estimates' % (BASE_URL, stock))
    chart_div = html_tree.xpath("//div[@class='graphChart']")[0]
    name = chart_div.xpath("p[@class='chartSmalltitle']")[0].text_content()
    name_dict = set_dict_key_value(consensual_estimates_data, name, {})
    LOGGER.debug(name)
    labels = chart_div.xpath("div[@class='yLabels']/p[@class='yLabel']")
    for l in labels:
        texts = l.text_content().split('|')
        set_dict_key_value(name_dict, texts[0], texts[1])
        LOGGER.debug("\t%s=%s" % (texts[0].strip(), texts[1].strip()))
    return consensual_estimates_data


# #########################################################################################################################
def __get_info(name, fun, *args):
    try:
        return name, fun(*args)
    except:
        LOGGER.exception("Error getting %s", name)
        return name, {}
