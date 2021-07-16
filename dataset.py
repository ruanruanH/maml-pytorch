#!/usr/bin/env python3

"""
@author: Guangyi
@since: 2021-07-14
"""

import collections
import random

import cv2 as cv
import imgaug.augmenters as iaa
import numpy as np
import torch
from docset import DocSet
from torch.utils.data import IterableDataset
from tqdm import tqdm

DEFAULT_AUG = [
    iaa.CropToFixedSize(64, 64),
    iaa.Dropout([0.0, 0.01]),
    iaa.Sharpen((0.0, 0.1)),
    iaa.AddToBrightness((-10, 10)),
    iaa.AddToHue((-5, 5)),
    iaa.Fliplr(0.5)
]


class NKDataset(IterableDataset):

    def __init__(self, ds_path, image_size, num_ways, num_shots, transform=None):
        super(NKDataset, self).__init__()
        self._image_size = image_size if not isinstance(image_size, int) else (image_size, image_size)
        self._num_ways = num_ways
        self._num_shots = num_shots
        self._docs = collections.defaultdict(list)
        if isinstance(ds_path, str):
            ds_path = [ds_path]
        for ds_path_i in ds_path:
            with DocSet(ds_path_i, 'r') as ds:
                for doc in tqdm(ds, leave=False):
                    label = doc['label']
                    self._docs[label].append(doc)
        self._docs = list(self._docs.values())
        self._transform = iaa.Sequential(transform) if transform is not None else iaa.CenterCropToFixedSize(64, 64)

    def __getitem__(self, item):
        return self.__next__()

    def __iter__(self):
        return self

    def __next__(self):
        task = random.sample(self._docs, self._num_ways)
        task = [
            [{'image': doc['image'], 'label': label} for doc in random.sample(sample_list, self._num_shots * 2)]
            for label, sample_list in enumerate(task)
        ]

        support_task = []
        query_task = []
        for sample_list in task:
            support_task.extend(sample_list[:self._num_shots])
            query_task.extend(sample_list[self._num_shots:])

        return self._collate(support_task), self._collate(query_task)

    def _collate(self, doc_list):
        image_list = []
        label_list = []
        for doc in doc_list:
            image = doc['image']
            if isinstance(image, bytes):
                image = cv.imdecode(np.frombuffer(image, np.byte), cv.IMREAD_COLOR)
                image = cv.cvtColor(image, cv.COLOR_BGR2RGB)
            if self._image_size is not None:
                image = cv.resize(image, self._image_size)
            if callable(self._transform):
                image = self._transform(image=image)
            image = torch.from_numpy(image)
            image = image.float() / 127.5 - 1.0
            image = image.permute((2, 0, 1))
            image_list.append(image)

            label_list.append(torch.tensor(doc['label'], dtype=torch.int64))

        return {
            'image': torch.stack(image_list),
            'label': torch.stack(label_list)
        }
