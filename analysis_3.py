import numpy as np
import cv2
from matplotlib import pyplot as plt
import timeit
import random
from threading import Thread
import click
import functools
import paramiko



MIN_MATCH_COUNT = 5 #10?

def get_keypoints(img, returnlist):
    print "Starting thread"
    sift = cv2.SIFT()
    kp, des = sift.detectAndCompute(img,None)
    Nkps = 1000
    if Nkps>=len(kp):
        Nkps = len(kp)
    print len(kp)
    indices = random.sample(range(len(kp)), Nkps)
    kp_short = []
    for index in indices:
        kp_short.append(kp[index])
    des_short = des[indices,:]
    returnlist.append(kp_short)
    returnlist.append(des_short)


def process_images(imgs): #first image is noflash, rest are with flash
    out_imgs = []
    threads = []
    threadData = []
    for img in imgs:
        data = []
        threadData.append(data)
        t = Thread(target=get_keypoints,args=(img,data))
        threads.append(t)
        t.start()
        print "started"
    print "waiting for threads to finish"
    for t in threads:
        t.join()
    print "Threads Done"

    template = threadData[0]
    for td in threadData[1:]:
        print "Processing image"
        FLANN_INDEX_KDTREE = 0
        index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
        search_params = dict(checks = 50) #50
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(td[1],template[1],k=2)
        good = []
        for m,n in matches:
            if m.distance < 0.7*n.distance:
                good.append(m)
        if len(good)>MIN_MATCH_COUNT:
            src_pts = np.float32([ td[0][m.queryIdx].pt for m in good ]).reshape(-1,1,2)
            dst_pts = np.float32([ template[0][m.trainIdx].pt for m in good ]).reshape(-1,1,2)      
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,5.0)
        else:
            print "Not enough matches are found - %d/%d" % (len(good),MIN_MATCH_COUNT)
            matchesMask = None #TODO Handle poor match. Repeat but remove fewer points?
        rows,cols = img.shape #TODO GET RIGHT IMAGE!
        out = cv2.warpPerspective(img, M, (cols,rows))
        #out = img
        out_imgs.append( out*1.0 - imgs[0]*1.0 )
    return out_imgs

class AllowAnythingPolicy(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        return
    
def my_callback(filename, bytes_so_far, bytes_total):
    print 'Transfer of %r is at %d/%d bytes (%.1f%%)' % (
        filename, bytes_so_far, bytes_total, 100. * bytes_so_far / bytes_total)

def get_connection(host,username,password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(AllowAnythingPolicy())
    client.connect(host, username=username, password=password)

def list_runs(host):
    client = get_connection(host,'pi','raspberry')
    sftp = client.open_sftp()
    sftp.chdir('/home/pi/beeimages')
        
    for filename in sorted(sftp.listdir()):
        print filename
        #if filename.startswith('20'):
        #    callback_for_filename = functools.partial(my_callback, filename)
        #    sftp.get(filename, filename, callback=callback_for_filename)
    client.close()
    
def download_files(host, run):
    client = get_connection(host,'pi','raspberry')
    sftp = client.open_sftp()
    sftp.chdir('/home/pi/beeimages')
        
    for filename in sorted(sftp.listdir()):
        print filename
        #if filename.startswith('20'):
        #    callback_for_filename = functools.partial(my_callback, filename)
        #    sftp.get(filename, filename, callback=callback_for_filename)
    client.close()


@click.command()
@click.option('--host')
@click.option('--list-runs', 'command', flag_value='list_runs', default=True)
@click.option('--process')
def hello(host,command, process):
    """Interfaces with the raspberry pi and processes bee photos"""
    if command=='list_runs':
        list_runs(host)
    print command
    
if __name__ == '__main__':
    hello()
