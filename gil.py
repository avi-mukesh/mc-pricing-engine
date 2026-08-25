from multiprocessing import Pool
from threading import Thread
from time import time
COUNT = 50000000

def countdown(n):
    while n>0:
        n-=1


if __name__=='__main__':
    # pool = Pool(processes=2)
    # start = time()
    # pool.apply_async(countdown, [COUNT//2])
    # pool.apply_async(countdown, [COUNT//2])
    # pool.close()
    # pool.join()
    # end = time()
    
    t1 = Thread(target=countdown, args=(COUNT//2,))
    t2 = Thread(target=countdown, args=(COUNT//2,))
    start = time()
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    end = time()
    
    
    print(end - start)
    