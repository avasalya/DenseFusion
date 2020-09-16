import torch.utils.data as data
from PIL import Image
import os
import os.path
import errno
import torch
import json
import codecs
import numpy as np
import sys
import torchvision.transforms as transforms
import argparse
import json
import time
import random
import numpy.ma as ma
import copy
import scipy.misc
import scipy.io as scio
import yaml
import cv2


def draw(img, imgpts, label):

    color = [[254,100,33],[254,244,0],[171,242,0],[0,216,254],[1,0,254],[95,0,254],[254,0,221],[0,0,0],[153,56,0],[138,36,124],[107,153,0],[5,0,153],[76,76,76],[32,153,67],[41,20,240],[230,111,240],[211,222,6],[40,233,70],[130,24,70],[244,200,210],[70,80,90],[30,40,30]]

    for point in imgpts:
        img=cv2.circle(img,(int(point[0][0]),int(point[0][1])), 1, color[int(label)], -1)

    return img

class PoseDataset(data.Dataset):

    def __init__(self, mode, num, add_noise, root, noise_trans, refine):
        onigiriObj = 1
        self.objlist = [onigiriObj]
        self.mode = mode

        self.list_rgb = []
        self.list_depth = []
        self.list_label = []
        self.list_obj = []
        self.list_frame = []
        self.meta = {}
        self.pt = {}
        self.root = root
        self.noise_trans = noise_trans
        self.refine = refine

        item_count = 0
        for item in self.objlist:
            if self.mode == 'train':
                input_file = open('{0}/data/{1}/train.txt'.format(self.root, '%02d' % item))
            else:
                input_file = open('{0}/data/{1}/test.txt'.format(self.root, '%02d' % item))
            while 1:
                item_count += 1
                input_line = input_file.readline()
                if self.mode == 'test' and item_count % 1 != 0:
                    continue
                if not input_line:
                    break
                if input_line[-1:] == '\n':
                    input_line = input_line[:-1]
                self.list_rgb.append('{0}/data/{1}/rgb/{2}.png'.format(self.root, '%02d' % item, input_line))
                self.list_depth.append('{0}/data/{1}/depth/{2}.png'.format(self.root, '%02d' % item, input_line))
                if self.mode == 'eval':
                    self.list_label.append('{0}/segnet_results/{1}_label/{2}_label.png'.format(self.root, '%02d' % item, input_line))
                else:
                    self.list_label.append('{0}/data/{1}/mask/{2}.png'.format(self.root, '%02d' % item, input_line))

                self.list_obj.append(item)
                self.list_frame.append(int(input_line))

            meta_file = open('{0}/data/{1}/gt.yml'.format(self.root, '%02d' % item), 'r')
            self.meta[item] = yaml.load(meta_file, Loader=yaml.SafeLoader)
            self.pt[item] = ply_vtx('{0}/models/obj_{1}.ply'.format(self.root, '%02d' % item))
            print("Object {0} buffer loaded".format(item))

        self.length = len(self.list_rgb)

        # camera _color_info
        self.cam_fx = 605.2861938476562
        self.cam_cx = 320.0749206542969
        self.cam_fy = 605.69921875
        self.cam_cy = 247.87693786621094

        self.xmap = np.array([[j for i in range(640)] for j in range(480)])
        self.ymap = np.array([[i for i in range(640)] for j in range(480)])

        self.num = num
        self.add_noise = add_noise
        self.trancolor = transforms.ColorJitter(0.2, 0.2, 0.2, 0.05)
        self.norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        self.border_list = [-1, 40, 80, 120, 160, 200, 240, 280, 320, 360, 400, 440, 480, 520, 560, 600, 640, 680]
        self.num_pt_mesh_large = 500
        self.num_pt_mesh_small = 500
        self.symmetry_obj_idx = [] #[onigiriObj]



    # index being the index from train.txt or test.txt
    def __getitem__(self, index):

        scale = 1000.0
        img = Image.open(self.list_rgb[index])
        depth = np.array(Image.open(self.list_depth[index]))
        label = np.array(Image.open(self.list_label[index]))
        obj = self.list_obj[index]
        frame = self.list_frame[index]
        # print("frame at index in train.txt", index+1, frame)

        meta = self.meta[obj][frame][0]

        mask_depth = ma.getmaskarray(ma.masked_not_equal(depth, 0))

        if self.mode == 'eval':
            mask_label = ma.getmaskarray(ma.masked_equal(label, np.array(255)))
        else:
            mask_label = ma.getmaskarray(ma.masked_equal(label, np.array(255)))
            # mask_label = ma.getmaskarray(ma.masked_equal(label, np.array([255, 255, 255])))[:,:,0]

        mask = mask_label * mask_depth

        if self.add_noise:
            img = self.trancolor(img)

        img = np.array(img)[:, :, :3]
        img = np.transpose(img, (2, 0, 1))
        img_masked = img

        if self.mode == 'eval':
            rmin, rmax, cmin, cmax = get_bbox(mask_to_bbox(mask_label))
        else:
            rmin, rmax, cmin, cmax = get_bbox(meta['obj_bb'])

        img_masked = img_masked[:, rmin:rmax, cmin:cmax]

        target_r = np.resize(np.array(meta['cam_R_m2c']), (3, 3))
        target_t = np.array(meta['cam_t_m2c'])
        add_t = np.array([random.uniform(-self.noise_trans, self.noise_trans) for i in range(3)])

        choose = mask[rmin:rmax, cmin:cmax].flatten().nonzero()[0]
        if len(choose) == 0:
            cc = torch.LongTensor([0])
            return(cc, cc, cc, cc, cc, cc)

        if len(choose) > self.num:
            c_mask = np.zeros(len(choose), dtype=int)
            c_mask[:self.num] = 1
            np.random.shuffle(c_mask)
            choose = choose[c_mask.nonzero()]
        else:
            choose = np.pad(choose, (0, self.num - len(choose)), 'wrap')

        depth_masked = depth[rmin:rmax, cmin:cmax].flatten()[choose][:, np.newaxis].astype(np.float32)
        xmap_masked = self.xmap[rmin:rmax, cmin:cmax].flatten()[choose][:, np.newaxis].astype(np.float32)
        ymap_masked = self.ymap[rmin:rmax, cmin:cmax].flatten()[choose][:, np.newaxis].astype(np.float32)
        choose = np.array([choose])

        cam_scale = 1.0
        pt2 = depth_masked / cam_scale
        pt0 = (ymap_masked - self.cam_cx) * pt2 / self.cam_fx
        pt1 = (xmap_masked - self.cam_cy) * pt2 / self.cam_fy
        cloud = np.concatenate((pt0, pt1, pt2), axis=1)
        cloud = cloud /scale
        if self.add_noise:
            cloud = np.add(cloud, add_t)


        model_points = self.pt[obj] / scale
        dellist = [j for j in range(0, len(model_points))]
        dellist = random.sample(dellist, len(model_points) - self.num_pt_mesh_small)
        model_points = np.delete(model_points, dellist, axis=0)


        target = np.dot(model_points, target_r.T)
        if self.add_noise:
            out_t = target_t / scale + add_t
            target = np.add(target, out_t)
        else:
            out_t = target_t / scale
            target = np.add(target, out_t)




        """ for debugging purposes  """

        ## saving masked bounding bbox cropped images
        # p_img = np.transpose(img_masked, (1, 2, 0))
        # scipy.misc.imsave('eval_result/{0}_input.png'.format(index), p_img)


        # fw = open('eval_result/{0}_cld.xyz'.format(index), 'w')
        # for it in cloud:
        #    fw.write('{0} {1} {2}\n'.format(it[0], it[1], it[2]))
        # fw.close()


        # fw = open('eval_result/{0}_model.xyz'.format(index), 'w')
        # for it in model_points:
        #    fw.write('{0} {1} {2}\n'.format(it[0], it[1], it[2]))
        # fw.close()


        # fw = open('eval_result/{0}_tar.xyz'.format(index), 'w')
        # for it in target:
        #    fw.write('{0} {1} {2}\n'.format(it[0], it[1], it[2]))
        # fw.close()



        # dist = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
        # cam_mat = np.matrix([
        #                     [self.cam_fx, 0, self.cam_cx],
        #                     [0, self.cam_fy, self.cam_cy],
        #                     [0, 0, 1]])

        # img = Image.open(self.list_rgb[index])
        # imgc = img.copy()
        # imgt = img.copy()
        # imgm = img.copy()
        # # scipy.misc.imsave('eval_result/{0}_rgb.png'.format(index), img)

        # # cloud
        # # imgpts_cloud, jac = cv2.projectPoints(cloud, target_r, target_t, cam_mat, dist)
        # imgpts_cloud, jac = cv2.projectPoints(cloud, np.eye(3), np.zeros(shape=target_t.shape), cam_mat, dist)
        # imgc = cv2.polylines(np.array(imgc), np.int32([np.squeeze(imgpts_cloud)]), True, (125, 125, 255))
        # scipy.misc.imsave('eval_result/{0}_imgpts_cloud2.png'.format(index), imgc)
        # # image_cloud = draw(imgc, imgpts_cloud, 2)
        # # scipy.misc.imsave('eval_result/{0}_imgpts_cloud.png'.format(index), image_cloud)

        # # model (read directly in from .xyz file)
        # imgpts_model, jac = cv2.projectPoints(model_points, target_r, target_t, cam_mat, dist)
        # imgm = cv2.polylines(np.array(imgm), np.int32([np.squeeze(imgpts_model)]), True, (0, 124, 255))
        # scipy.misc.imsave('eval_result/{0}_imgpts_model2.png'.format(index), imgm)
        # # image_model = draw(imgm, imgpts_model, 2)
        # # scipy.misc.imsave('eval_result/{0}_imgpts_model.png'.format(index), image_model)

        # # target
        # imgpts_target, jac = cv2.projectPoints(target, np.eye(3), np.zeros(shape=target_t.shape), cam_mat, dist)
        # imgt = cv2.polylines(np.array(imgt), np.int32([np.squeeze(imgpts_target)]), True, (0, 124, 255))
        # scipy.misc.imsave('eval_result/{0}_imgpts_target2.png'.format(index), imgt)
        # # image_target = draw(imgt, imgpts_target, 2)
        # # scipy.misc.imsave('eval_result/{0}_imgpts_target.png'.format(index), image_target)


        return torch.from_numpy(cloud.astype(np.float32)), \
            torch.LongTensor(choose.astype(np.int32)), \
            self.norm(torch.from_numpy(img_masked.astype(np.float32))), \
            torch.from_numpy(target.astype(np.float32)), \
            torch.from_numpy(model_points.astype(np.float32)), \
            torch.LongTensor([self.objlist.index(obj)])




    def __len__(self):
        return self.length

    def get_sym_list(self):
        return self.symmetry_obj_idx

    def get_num_points_mesh(self):
        if self.refine:
            return self.num_pt_mesh_large
        else:
            return self.num_pt_mesh_small



border_list = [-1, 40, 80, 120, 160, 200, 240, 280, 320, 360, 400, 440, 480, 520, 560, 600, 640, 680]
img_width = 480
img_length = 640


def mask_to_bbox(mask):
    mask = mask.astype(np.uint8)
    _, contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    x = 0
    y = 0
    w = 0
    h = 0
    for contour in contours:
        tmp_x, tmp_y, tmp_w, tmp_h = cv2.boundingRect(contour)
        if tmp_w * tmp_h > w * h:
            x = tmp_x
            y = tmp_y
            w = tmp_w
            h = tmp_h
    return [x, y, w, h]

def get_bbox(bbox):
    bbx = [bbox[1], bbox[1] + bbox[3], bbox[0], bbox[0] + bbox[2]]
    if bbx[0] < 0:
        bbx[0] = 0
    if bbx[1] >= 480:
        bbx[1] = 479
    if bbx[2] < 0:
        bbx[2] = 0
    if bbx[3] >= 640:
        bbx[3] = 639
    rmin, rmax, cmin, cmax = bbx[0], bbx[1], bbx[2], bbx[3]
    r_b = rmax - rmin
    for tt in range(len(border_list)):
        if r_b > border_list[tt] and r_b < border_list[tt + 1]:
            r_b = border_list[tt + 1]
            break
    c_b = cmax - cmin
    for tt in range(len(border_list)):
        if c_b > border_list[tt] and c_b < border_list[tt + 1]:
            c_b = border_list[tt + 1]
            break
    center = [int((rmin + rmax) / 2), int((cmin + cmax) / 2)]
    rmin = center[0] - int(r_b / 2)
    rmax = center[0] + int(r_b / 2)
    cmin = center[1] - int(c_b / 2)
    cmax = center[1] + int(c_b / 2)
    if rmin < 0:
        delt = -rmin
        rmin = 0
        rmax += delt
    if cmin < 0:
        delt = -cmin
        cmin = 0
        cmax += delt
    if rmax > 480:
        delt = rmax - 480
        rmax = 480
        rmin -= delt
    if cmax > 640:
        delt = cmax - 640
        cmax = 640
        cmin -= delt
    return rmin, rmax, cmin, cmax

def ply_vtx(path):
    f = open(path)
    assert f.readline().strip() == "ply"
    f.readline()
    f.readline()
    N = int(f.readline().split()[-1])
    while f.readline().strip() != "end_header":
        continue
    pts = []
    for _ in range(N):
        pts.append(np.float32(f.readline().split()[:3]))
    return np.array(pts)
