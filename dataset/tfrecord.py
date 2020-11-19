import struct
import cv2
import numpy as np
from .tfrecord_utils import yt_example_pb2
import torch
import torch.utils.data as data
import torchvision.transforms as transforms
import utils.my_transforms as my_transforms
import os


class TFRecordDataset(data.Dataset):
    def __init__(self, root='/raid/home/fufuyu/dataset/',
                 dataname='market1501', part='train',
                 least_image_per_class=4,
                 size=(384, 128), prng=np.random, **kwargs):
        self.names = dataname
        self.tfrecord_root = root
        self.mode = part
        self.getFileList()  #self.filelist, self.labellist =
        self.logger = kwargs.get('logger', print)
        self.return_cam = kwargs.get('return_cam', False)

        self.transform = transforms.Compose([
            transforms.Resize(size),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])
        ])

        if self.mode == 'train':
            self.transform = transforms.Compose([
                transforms.RandomHorizontalFlip(),
                transforms.Resize(size),
                transforms.Pad(10),
                transforms.RandomCrop(size),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225]),
                my_transforms.RandomErasing(mean=[0.485, 0.456, 0.406]
                                            ),

            ])


    def getFileList(self):
        self.filelist, self.labellist = [], []
        self.label_offset = 0
        for idx in self.names:
            index_filepath = os.path.join(self.tfrecord_root, idx, idx + '.txt')
            with open(index_filepath, "r") as idx_r:
                for line in idx_r:
                    data_name, tf_num, offset, label = line.rstrip().split('\t')[:4]
                    # file_name = '{0}*{1:05}*{2}'.format(data_name, int(tf_num), offset)
                    file_name = (data_name, str(tf_num).zfill(5), offset)
                    self.filelist.append(file_name)
                    label = int(label) + self.label_offset
                    self.labellist.append(label)
            self.label_offset = max(self.labellist)


    def get_file_loc(self, index):
        return self.filelist[index]

    def get_label(self, index):
        return self.labellist[index]

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            tuple: (image, target) where target is class_index of the target class.
        """
        file_loc, label = self.get_file_loc(index), self.get_label(index)
        src_img = self.getImageData(file_loc)
        img = cv2.imdecode(np.asarray(bytearray(src_img), dtype=np.uint8), 1)
        img = img[:, :, ::-1]
        img, mirrored = self.transform(img)

        return img, label

    def __len__(self):
        return len(self.filelist)

    def getImageData(self, file_loc):
        data_name, tf_num, offset = file_loc
        tf_file = self.tfrecord_root + "/remote_tfrecord" + "/" + data_name + "/" + data_name + "-" + tf_num + ".tfrecord"

        with open(tf_file, 'rb') as tf:
            tf.seek(int(offset))
            pb_len_bytes = tf.read(8)
            if len(pb_len_bytes) < 8:
                print("read pb_len_bytes err,len(pb_len_bytes)=" +
                      str(len(pb_len_bytes)))
                return None

            pb_len = struct.unpack('L', pb_len_bytes)[0]

            len_crc_bytes = tf.read(4)
            if len(len_crc_bytes) < 4:
                print("read len_crc_bytes err,len(len_crc_bytes)=" +
                      str(len(len_crc_bytes)))
                return None

            len_crc = struct.unpack('I', len_crc_bytes)[0]

            pb_data = tf.read(pb_len)
            if len(pb_data) < pb_len:
                print("read pb_data err,len(pb_data)=" + str(len(pb_data)))
                return None

            data_crc_bytes = tf.read(4)
            if len(data_crc_bytes) < 4:
                print("read data_crc_bytes err,len(data_crc_bytes)=" +
                      str(len(data_crc_bytes)))
                return None

            data_crc = struct.unpack('I', data_crc_bytes)[0]

            example = yt_example_pb2.Example()
            example.ParseFromString(pb_data)

            image_data_feature = example.features.feature.get("image")
            label_feature = example.features.feature.get("label")

            if image_data_feature:
                image_data = image_data_feature.bytes_list.value[0]
                return image_data
