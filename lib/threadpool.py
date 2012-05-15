# -*- coding: utf-8 -*-

import threading
import Queue
import time
import random
from headphones import logger

NUMBER_OF_WORKERS = 10
WORK_QUEUE = Queue.Queue()
QUEUE_LOCK = threading.Lock()


def put(pointer, kwargs = {}):
  logger.debug('Adding a job to the work queue, the kwargs are: %s' % kwargs)
  WORK_QUEUE.put( { 'pointer': pointer, 'kwargs': kwargs } )


class WorkerQueue(threading.Thread):
  def __init__(self, queue):
    self.__queue = queue

    threading.Thread.__init__(self)


  def run(self):
    while True:
      with QUEUE_LOCK:
        work_item = self.__queue.get()

      if work_item is None:
        logger.debug('Thread-%s: SLEEPING FOR A SECOND' % threading.currentThread().ident)

        time.sleep(1000) # Sleep for a second if there is nothing in the queue.
      else:
        logger.debug('Thread-%s: Working...' % threading.currentThread().ident)
        logger.debug('Thread-%s: Kwargs: %s' % (threading.currentThread().ident, work_item['kwargs']))
        logger.debug('Thread-%s: QueueSize: %s' % (threading.currentThread().ident, self.__queue.qsize()))

        # Execute the work item, passing it the arguments...
        work_item['pointer']( **work_item['kwargs'] )
        self.__queue.task_done()


# Spin up workers for each NUMBER_OF_WORKERS defined to pull work-items off of 
# the WORK_QUEUE.
for i in range(NUMBER_OF_WORKERS):
  WorkerQueue(WORK_QUEUE).start()
