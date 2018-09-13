# -*- coding: utf-8 -*-
"""
Created on Thu Sep 07 10:06:23 2017

@author: Wenyuan Li

Functions that help write images and annotations into tfrecord.
"""

# Important: We are using PIL to read .png files later.
# This was done on purpose to read indexed png files
# in a special way -- only indexes and not map the indexes
# to actual rgb values. This is specific to PASCAL VOC
# dataset data. If you don't want thit type of behaviour
# consider using skimage.io.imread()
from PIL import Image
import numpy as np
#import skimage.io as io
import tensorflow as tf

# Helper functions for defining tf types
def _bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


def _int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))


def write_image_annotation_pairs_to_tfrecord(filename_pairs, tfrecords_filename):
    """Writes given image/annotation pairs to the tfrecords file.
    The function reads each image/annotation pair given filenames
    of image and respective annotation and writes it to the tfrecord
    file.
    Parameters
    ----------
    filename_pairs : array of tuples (img_filepath, annotation_filepath)
        Array of tuples of image/annotation filenames
    tfrecords_filename : string
        Tfrecords filename to write the image/annotation pairs
    """
    def _crop_split_image(img_org, annotation_org, height, width):
        
        imgheight, imgwidth, _ = img_org.shape
        annheight, annwidth = annotation_org.shape
        assert imgwidth == annwidth and imgheight == annheight, "The image and annotation size don't match!"
        
        img = []
        ann = []
        for i in range(0, imgheight - 101, 100):
            for j in range(0, imgwidth - 101, 100):
                img_temp = img_org[i : i + height, j : j + height, :]
                img.append(img_temp)
                ann_temp = annotation_org[i : i + height, j : j + height]
                ann.append(ann_temp)
        return img, ann
    
    def _image_padding(img_org, annotation_org):
        img_pad = np.lib.pad(img_org, ((50,50),(50,50), (0, 0)), 'symmetric')
        ann_pad = np.lib.pad(annotation_org, ((50, 50), (50, 50)), 'symmetric') 
        return img_pad, ann_pad
        
    
    
    writer = tf.python_io.TFRecordWriter(tfrecords_filename)
    for img_path, annotation_path in filename_pairs:
        
        img_org = np.array(Image.open(img_path))
        annotation_org = np.array(Image.open(annotation_path))
        # crop the img and annotation to 200x200
        img_pad, ann_pad = _image_padding(img_org, annotation_org)
        img_crop, ann_crop = _crop_split_image(img_pad, ann_pad, 200, 200)
        
        
        
        for img, annotation in zip(img_crop, ann_crop):
            
            height = img.shape[0]
            width = img.shape[1]
            img_raw = img.tostring()
            annotation_raw = annotation.tostring()
    
            example = tf.train.Example(features=tf.train.Features(feature={
                'height': _int64_feature(height),
                'width': _int64_feature(width),
                'image_raw': _bytes_feature(img_raw),
                'mask_raw': _bytes_feature(annotation_raw)}))
    
            writer.write(example.SerializeToString())

    writer.close()


def read_image_annotation_pairs_from_tfrecord(tfrecords_filename):
    """Return image/annotation pairs from the tfrecords file.
    The function reads the tfrecords file and returns image
    and respective annotation matrices pairs.
    Parameters
    ----------
    tfrecords_filename : string
        filename of .tfrecords file to read from
    
    Returns
    -------
    image_annotation_pairs : array of tuples (img, annotation)
        The image and annotation that were read from the file
    """
    
    image_annotation_pairs = []

    record_iterator = tf.python_io.tf_record_iterator(path=tfrecords_filename)

    for string_record in record_iterator:

        example = tf.train.Example()
        example.ParseFromString(string_record)

        height = int(example.features.feature['height']
                                     .int64_list
                                     .value[0])

        width = int(example.features.feature['width']
                                    .int64_list
                                    .value[0])

        img_string = (example.features.feature['image_raw']
                                      .bytes_list
                                      .value[0])

        annotation_string = (example.features.feature['mask_raw']
                                    .bytes_list
                                    .value[0])

        img_1d = np.fromstring(img_string, dtype=np.uint8)
        img = img_1d.reshape((height, width, -1))

        annotation_1d = np.fromstring(annotation_string, dtype=np.uint8)

        annotation = annotation_1d.reshape((height, width, -1))

        image_annotation_pairs.append((img, annotation))
    
    return image_annotation_pairs


def read_tfrecord_and_decode_into_image_annotation_pair_tensors(tfrecord_filenames_queue):
    """Return image/annotation tensors that are created by reading tfrecord file.
    The function accepts tfrecord filenames queue as an input which is usually
    can be created using tf.train.string_input_producer() where filename
    is specified with desired number of epochs. This function takes queue
    produced by aforemention tf.train.string_input_producer() and defines
    tensors converted from raw binary representations into
    reshaped image/annotation tensors.
    Parameters
    ----------
    tfrecord_filenames_queue : tfrecord filename queue
        String queue object from tf.train.string_input_producer()
    
    Returns
    -------
    image, annotation : tuple of tf.int32 (image, annotation)
        Tuple of image/annotation tensors
    """
    
    reader = tf.TFRecordReader()

    _, serialized_example = reader.read(tfrecord_filenames_queue)

    features = tf.parse_single_example(
      serialized_example,
      features={
        'height': tf.FixedLenFeature([], tf.int64),
        'width': tf.FixedLenFeature([], tf.int64),
        'image_raw': tf.FixedLenFeature([], tf.string),
        'mask_raw': tf.FixedLenFeature([], tf.string)
        })

    
    image = tf.decode_raw(features['image_raw'], tf.uint8)
    annotation = tf.decode_raw(features['mask_raw'], tf.uint8)
    
    height = tf.cast(features['height'], tf.int32)
    width = tf.cast(features['width'], tf.int32)
    
    image_shape = tf.stack([height, width, 3])
    
    # The last dimension was added because
    # the tf.resize_image_with_crop_or_pad() accepts tensors
    # that have depth. We need resize and crop later.
    # TODO: See if it is necessary and probably remove third
    # dimension
    annotation_shape = tf.stack([height, width, 1])
    
    image = tf.reshape(image, image_shape)
    annotation = tf.reshape(annotation, annotation_shape)
    
    return image, annotation