# Copyright 2023 antillia.com Toshiyuki Arai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# ImageMaskDatasetGenerator.py
# 2023/08/20 to-arai
# 2024/05/10 Fixed spelling errors.
import os
import shutil
import numpy as np
import cv2
import glob
import random
#from matplotlib import pyplot as plt

import traceback
from ConfigParser import ConfigParser
from ImageMaskAugmentor import ImageMaskAugmentor

class ImageMaskDatasetGenerator:

  def __init__(self, config_file, dataset=ConfigParser.TRAIN, seed=137):
    random.seed = seed

    config = ConfigParser(config_file)
    self.image_width    = config.get(ConfigParser.MODEL, "image_width")
    self.image_height   = config.get(ConfigParser.MODEL, "image_height")
    self.image_channels = config.get(ConfigParser.MODEL, "image_channels")
    
    self.train_dataset  = [config.get(ConfigParser.TRAIN, "image_datapath"),
                          config.get(ConfigParser.TRAIN, "mask_datapath")]
    
    self.eval_dataset   = [config.get(ConfigParser.EVAL, "image_datapath"),
                          config.get(ConfigParser.EVAL, "mask_datapath")]

    self.batch_size     = config.get(ConfigParser.TRAIN, "batch_size")
    self.binarize       = config.get(ConfigParser.MASK, "binarize")
    self.threshold      = config.get(ConfigParser.MASK, "threshold")
    self.blur_mask      = config.get(ConfigParser.MASK, "blur")
    # 2024/07/19
    self.color_converter  = config.get(ConfigParser.IMAGE, "color_converter", dvalue=None)
    if self.color_converter != None:
      self.color_converter  = eval(self.color_converter)
    # 2024/08/18
    self.gamma  = config.get(ConfigParser.IMAGE, "gamma", dvalue=0)
    # 2024/08/20
    self.sharpen_k =  config.get(ConfigParser.IMAGE, "sharpening", dvalue=0)

    #Fixed blur_size
    self.blur_size = (3, 3)
    if not dataset in [ConfigParser.TRAIN, ConfigParser.EVAL]:
      raise Exception("Invalid dataset")
      
    image_datapath = None
    mask_datapath  = None
  
    [image_datapath, mask_datapath] = self.train_dataset
    if dataset == ConfigParser.EVAL:
      [image_datapath, mask_datapath] = self.eval_dataset

    image_files  = glob.glob(image_datapath + "/*.jpg")
    image_files += glob.glob(image_datapath + "/*.png")
    image_files += glob.glob(image_datapath + "/*.bmp")
    image_files += glob.glob(image_datapath + "/*.tif")
    image_files  = sorted(image_files)

    mask_files   = None
    if os.path.exists(mask_datapath):
      mask_files  = glob.glob(mask_datapath + "/*.jpg")
      mask_files += glob.glob(mask_datapath + "/*.png")
      mask_files += glob.glob(mask_datapath + "/*.bmp")
      mask_files += glob.glob(mask_datapath + "/*.tif")
      mask_files  = sorted(mask_files)
      
      if len(image_files) != len(mask_files):
        raise Exception("FATAL: Images and masks unmatched")
      
    num_images  = len(image_files)
    if num_images == 0:
      raise Exception("FATAL: Not found image files")
    
    self.image_datapath = image_datapath
    self.mask_datapath  = mask_datapath
    
    self.master_image_files    = image_files
    self.master_mask_files     = mask_files
    self.generated_images_dir  = config.get(ConfigParser.GENERATOR, "generated_images_dir", dvalue="./generated_images_dir")
    self.generated_masks_dir   = config.get(ConfigParser.GENERATOR, "generated_masks_dir",  dvalue="./generated_masks_dir")
    self.debug                 = config.get(ConfigParser.GENERATOR, "debug",        dvalue=True)
    self.augmentation          = config.get(ConfigParser.GENERATOR, "augmentation", dvalue=True)
    if self.debug:
      if os.path.exists(self.generated_images_dir):
        shutil.rmtree(self.generated_images_dir) 
      if not os.path.exists(self.generated_images_dir):
        os.makedirs(self.generated_images_dir) 

      if os.path.exists(self.generated_masks_dir):
        shutil.rmtree(self.generated_masks_dir) 
      if not os.path.exists(self.generated_masks_dir):
        os.makedirs(self.generated_masks_dir) 

    self.image_mask_augmentor = ImageMaskAugmentor(config_file)

  # 2024/08/18
  def gamma_correction(self, image, gamma):
    table = (np.arange(256) / 255) ** gamma * 255
    table = np.clip(table, 0, 255).astype(np.uint8)
    return cv2.LUT(image, table)
  
  def random_sampling(self, batch_size):
    if batch_size < len(self.master_image_files):
      images_sample = random.sample(self.master_image_files, batch_size)
    else:
      print("==- batch_size > the number of master_image_files")
      #if batch_size > the number of maste_image_files
      # we cannot apply random.sample function.
      #images_sample = random.sample(self.master_image_files, len_samples)
      images_sample = self.master_image_files
      # Force augmentation to be True
      self.augmentation = True
    
      self.image_mask_augmentor.rotation= True
      self.image_mask_augmentor.hflip   = True
      self.image_mask_augmentor.vflip   = True
      
    masks_sample  = []
    for image_file in images_sample:
      basename  = os.path.basename(image_file)
      mask_file = os.path.join(self.mask_datapath, basename)
      if os.path.exists(mask_file):
        masks_sample.append(mask_file)
      else:
        raise Exception("Not found " + mask_file)
    images_sample = sorted(images_sample)
    masks_sample  = sorted(masks_sample)
    #print("  {}".format(images_sample))
    #print("  {}".format(masks_sample))

    return (images_sample, masks_sample)

  def generate(self):
    print("---ImageMaskDatasetGenerator.generate batch_size {}".format(self.batch_size))
    with open("./generate_images.txt", "w", encoding="utf-8") as f:
      while True:
        (self.image_files, self.mask_files) = self.random_sampling(self.batch_size)

        IMAGES = []
        MASKS  = []
        for n, image_file in enumerate(self.image_files):
          mask_file = self.mask_files[n]
          image_basename = os.path.basename(image_file)
          mask_basename  = os.path.basename(mask_file)
          #print("ImageMaskDatasetGenerator {} {} {}".format(n, image_basename, mask_basename))

          f.writelines(str(n) + "_" + image_basename + "_" + mask_basename + "\n")
          image = cv2.imread(image_file)
          # 2024/07/18
          if self.color_converter!=None:
            image = cv2.cvtColor(image, self.color_converter) ##cv2.COLOR_BGR2HLS)
          if self.gamma !=0:
            image = self.gamma_correction(image, self.gamma)
          if self.sharpen_k >0:
            k = self.sharpen_k
            kernel = np.array([[-k, -k, -k], 
                       [-k, 1+8*k, -k], 
                       [-k, -k, -k]])
            image = cv2.filter2D(image, ddepth=-1, kernel=kernel)

          h, w, c = image.shape
          #print("---image.shape {}".format(image.shape))
          if h != self.image_height and w != self.image_width:
            image = cv2.resize(image, dsize= (self.image_height, self.image_width), interpolation=cv2.INTER_NEAREST)

          IMAGES.append(image)
          if self.debug:
            filepath = os.path.join(self.generated_images_dir, image_basename)
            cv2.imwrite(filepath, image)
          mask  = cv2.imread(mask_file)
          h, w, c = mask.shape

          mask  = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
          if h != self.image_height and w != self.image_width:

            mask  = cv2.resize(mask, dsize= (self.image_height, self.image_width),   interpolation=cv2.INTER_NEAREST)

          # Binarize mask
          if self.binarize:
            mask[mask< self.threshold] =   0  
            mask[mask>=self.threshold] = 255

          # Blur mask 
          if self.blur_mask:
            # 2024/06/25
            mask = cv2.GaussianBlur(mask, ksize=self.blur_size, sigmaX=0)
            #mask = cv2.blur(mask, self.blur_size)
  
          mask  = np.expand_dims(mask, axis=-1) 
          #print("mask shape {}".format(mask.shape))
          MASKS.append(mask)
          if self.debug:
            filepath = os.path.join(self.generated_masks_dir, mask_basename) 
            cv2.imwrite(filepath, mask)
          if self.augmentation:
            self.image_mask_augmentor.augment(IMAGES, MASKS, image, mask,
                                             self.generated_images_dir, image_basename,
                                             self.generated_masks_dir,  mask_basename )
        num_images = len(IMAGES)
        numbers = [i for i in range(num_images)]
        random.shuffle(numbers)
        
        if self.batch_size < num_images:
          target_numbers = random.sample(numbers, self.batch_size)
        else:
          target_numbers = numbers

        SELECTED_IMAGES = []
        SELECTED_MASKS  = [] 
        #print("--- target_numbers_len  {}  {}".format(len(target_numbers), target_numbers) )
        for i in target_numbers:
          SELECTED_IMAGES.append(IMAGES[i])
          SELECTED_MASKS.append(MASKS[i])
        
        (X, Y) = self.convert(SELECTED_IMAGES, SELECTED_MASKS)
        yield (X, Y)


  def convert(self, IMAGES, MASKS):
    ilen = len(IMAGES)
    mlen = len(MASKS)
    X = np.zeros((ilen, self.image_height, self.image_width, self.image_channels), dtype=np.uint8)
    Y = np.zeros((mlen, self.image_height, self.image_width, 1), dtype=bool)
    for i in range(ilen):
      X[i] = IMAGES[i]
      Y[i] = MASKS[i]
    return (X, Y)

  
  if __name__ == "__main__":

    try:
      config_file = "./train_eval_infer.config"
      generator = ImageMaskDatasetGenerator(config_file, dataset=ConfigParser.TRAIN)
      for i in range(10):
        generator.generate()

    except:

      traceback.print_exc()

