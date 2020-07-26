import urllib3
from lxml import html
import os
import logging
import boto3
import json

USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'
STOCK_PROCESS_QUEUE_NAME = os.environ['STOCK_PROCESS_QUEUE_NAME']

LOGGING_LEVEL = logging.getLevelName(os.environ['LOGGING_LEVEL'])
LOGGER = logging.getLogger()
LOGGER.setLevel(LOGGING_LEVEL)

sqs = boto3.resource('sqs')
stock_process_queue = sqs.get_queue_by_name(QueueName=STOCK_PROCESS_QUEUE_NAME)


def lambda_handler(event, context):
    LOGGER.debug("tickers collection triggered")
    LOGGER.debug("Received event %s and context %s", event, context)
    http_connection_pool = urllib3.PoolManager(cert_reqs='CERT_NONE')
    req = http_connection_pool.request(method='GET', url='https://br.investing.com/equities/StocksFilter',
                                       headers={'User-Agent': USER_AGENT})
    html_tree = html.fromstring(req.data.decode('utf-8'))
    stock_links_list = html_tree.xpath("//table[@id='cross_rate_markets_stocks_1']/tbody/tr/td[2]/a")
    for stock_link in stock_links_list[:2]:
        stock = stock_link.get('href').split('/')[-1]
        send_message_to_queue(stock)


def send_message_to_queue(stock_code):
    LOGGER.info("Sending stock %s to queue %s", stock_code, STOCK_PROCESS_QUEUE_NAME)
    stock_process_queue.send_message(MessageBody=json.dumps({'stock_code': stock_code}))

