import cv2 as cv

root = '../../../linemod/Linemod_preprocessed/data/02/'
path1 = root + 'rgb/0010.png'
path2 = root + 'depth/0010.png'
path3 = root + 'mask/0010.png'

imgrgb = cv.imread(path1)
imgmask = cv.imread(path2)
imgdepth = cv.imread(path3)

print(path1)
print(imgrgb.shape)
print(path2)
print(imgmask.shape)
print(path3)
print(imgdepth.shape)