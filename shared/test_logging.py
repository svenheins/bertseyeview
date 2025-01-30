import logging


import logging


def main():

    logging.basicConfig(filename='app.log', filemode='a',format='%(asctime)s - %(message)s', level=logging.INFO)
    logging.info('Admin logged in')
    logging.info('Admin logged in')
    logging.info('Admin logged in')


# __main__ function 
if __name__=="__main__": 
    main() 