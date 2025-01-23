#!/usr/bin/env python
# coding: utf-8


import requests
import mysql.connector as database_connect
import time
import datetime
import sys
import logging
import configparser


def connect_to_db():
    try:
        print(user, password, host, database)
        establish_connection = database_connect.connect(
            user=user,
            password=password,
            host=host,
            database=database)
        establish_cursor = establish_connection.cursor()
        print('Connected to database.')
        logging.info('Connected to database.')
        return establish_connection, establish_cursor
    except Exception as e:
        print(e)
        logging.error(e)


def get_data():
    tries = 10
    for i in range(tries):
        print(f'Getting data from inverter, try {i}')
        logging.info(f'Getting data from inverter, try {i}')
        try:
            r = requests.Session()
            r = requests.get(status_website_url, auth=(status_user_name, status_password), timeout=15)
            r.raise_for_status()
            print(r.text[:50] + ' ... ')
            logging.info(r.text[:50] + ' ... ')
            break
        except requests.exceptions.HTTPError as err:
            print(err)
            print('Attempting reconnect...')
            logging.warning(err)
            logging.info('Attempting reconnect...')
            try:
                r = requests.get(login_website_url, auth=(login_user_name, login_password))
            except:
                pass
        except requests.exceptions.ChunkedEncodingError as err:
            print(err)
            print('Retrying...')
            logging.error(err)
            logging.info('Retrying...')
        except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout) as err:
            print(err)
            logging.warning(err)
            while True:
                print(
                    'Connection lost, inverter is offline. Retry in 15 minutes... ' + time.strftime("%Y-%m-%d %H:%M:%S",
                                                                                                    time.localtime()))
                logging.warning(
                    'Connection lost, inverter is offline. Retry in 15 minutes... ' + time.strftime("%Y-%m-%d %H:%M:%S",
                                                                                                    time.localtime()))
                time.sleep(900.0 - ((time.monotonic() - starttime) % 900.0))
                try:
                    print('Retrying....')
                    logging.info('Retrying....')
                    r = requests.get(login_website_url, auth=(login_user_name, login_password), timeout=15)
                    r.raise_for_status()
                    print('Success.')
                    break
                except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as err:
                    print(err)
                    logging.error(err)
                except:
                    print('Other Error')
                    logging.error('Other Error')
                    pass
            try:
                r = requests.get(status_website_url, auth=(status_user_name, status_password), timeout=15)
                break
            except:
                pass
        finally:
            pass

    html = r.text
    index_start = html.find("var webdata_now_p = ") + len("var webdata_now_p = ") + 1
    index_end = html.find(";", index_start) - 1

    try:
        get_power_now = int(html[index_start:index_end])
    except ValueError as ve:
        print('Power Output was not found/not a number :' + str(ve))
        logging.error('Power Output was not found/not a number :' + str(ve))
        get_power_now = None
    return get_power_now


def add_data(use_connection, use_cursor, add_power_now, add_reading_utc_time):
    try:
        statement = "INSERT INTO inverterdata (Power, reading_utc_time) VALUES (%s, %s)"
        print(add_power_now, str(add_reading_utc_time))
        logging.info(str(add_power_now) + "W at " + str(add_reading_utc_time))
        data = (add_power_now, add_reading_utc_time)
        use_cursor.execute(statement, data)
        use_connection.commit()
        print("Successfully added entry to database at " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
        logging.info("Successfully added entry to database at " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
        return True
    except database_connect.Error as e:
        print(f"Error adding entry to database: {e}")
        logging.error(f"Error adding entry to database: {e}")
        return False


def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        # Will call default excepthook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
        # Create a critical level log message with info from the except hook.
    print("Unhandled exception", (exc_type, exc_value, exc_traceback))
    logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))


if __name__ == '__main__':
    # set up config parser to use ini poll_solar.ini
    config = configparser.ConfigParser()
    config.read(sys.path[0] + '/poll_solar.ini')
    # read variables from config
    user = config['Database']['user']
    password = config['Database']['password']
    host = config['Database']['host']
    database = config['Database']['database']

    status_website_url = config['Inverter']['status_website_url']
    status_user_name = config['Inverter']['status_user_name']
    status_password = config['Inverter']['status_password']
    login_website_url = config['Inverter']['login_website_url']
    login_user_name = config['Inverter']['login_user_name']
    login_password = config['Inverter']['login_password']

    # set up logger
    logging.basicConfig(filename=sys.path[0] + "/logs_solar.log", filemode="w",
                        format="%(asctime)s ? %(levelname)s: %(message)s", level=logging.INFO)
    logger = logging.getLogger('MyLogger')

    # set up exception handling
    sys.excepthook = handle_unhandled_exception

    # Connect to database
    print('Connecting, please wait...')
    connection, cursor = connect_to_db()
    starttime = time.monotonic()

    # Main Loop
    while True:
        # get power output data from inverter
        power_now = get_data()
        # get time
        reading_utc_time = datetime.datetime.now(datetime.timezone.utc)
        # add data to database if power output is valid
        if power_now is not None:
            success: bool = add_data(connection, cursor, power_now, reading_utc_time)
            # if there was no database connection, reconnect
            if not success:
                print('Could not add entry to database, attempting reconnect...')
                logging.error('Could not add entry to database, attempting reconnect...')
                connection, cursor = connect_to_db()
        else:
            print('Power Output not a number, will not be added to database, skipping...')
            logging.error('Power Output not a number, will not be added to database, skipping...')
        # sleep 3 minutes, then repeat
        time.sleep(180.0 - ((time.monotonic() - starttime) % 180.0))
