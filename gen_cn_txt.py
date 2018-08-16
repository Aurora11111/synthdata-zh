# -*- coding: utf-8 -*-

# Copyright (c) 2016 Matthew Earl
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the 'Software'), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
#     The above copyright notice and this permission notice shall be included
#     in all copies or substantial portions of the Software.
# 
#     THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS
#     OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#     MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
#     NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#     DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#     OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
#     USE OR OTHER DEALINGS IN THE SOFTWARE.



'''
Generate training and test images.

'''


__all__ = (
    'generate_ims',
)


import itertools
import math
import os
import random
import sys
import colorsys
import cv2
import numpy
import math
import time
import linecache
import argparse
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import common_cn


timestr = time.strftime('%Y_%m_%d',time.localtime(time.time()))
parser = argparse.ArgumentParser()
parser.add_argument('--bgs', default=None, help='path to backgrounds')
parser.add_argument('--fonts', default=None, help='path to fonts')
parser.add_argument('--fh', type=int, default=48, help='pixel size to which the chars are resized')
parser.add_argument('--output', default=None, help='path to create datasets')
parser.add_argument('--label', default='word.txt', help='path to words label')
parser.add_argument('--trainlabel', default=None, help='path to create train label')
parser.add_argument('--vallabel', default=None, help='path to create val label')
parser.add_argument('--sumnumber', type=int, default=5, help='number of word')
parser.add_argument('--trainnum', type=int, default=4, help='number of trainword')
parser.add_argument('--str', type=str,default=timestr, help='de for datasets')
opt = parser.parse_args()

if opt.bgs is None:
    opt.bgs = './bgs_10'
    try:
        os.path.exists(opt.bgs)
    except Exception as  e:
        print ("except:",e)
if opt.fonts is None:
    opt.fonts = './fonts_cn'
    try:
        os.path.exists(opt.fonts)
    except Exception as  e:
        print("except:", e)
if opt.output is None:
    opt.output = './datasets' 	
if not os.path.exists(opt.output):
    os.mkdir(opt.output) 
if opt.trainlabel is None:
    opt.trainlabel = './train.txt'
if opt.vallabel is None:
    opt.vallabel = './val.txt'
assert opt.trainnum <= opt.sumnumber	
print(opt)
	
BGS_DIR = opt.bgs
FONT_DIR = opt.fonts
FONT_HEIGHT = opt.fh 
R_OUTPUT_DIR = opt.output
WORD_TXT = opt.label
train_lable = opt.trainlabel
test_lable = opt.vallabel

def make_char_ims(font_path, output_height,font_color): 

    b = random.randint(30,50)
    font_size = output_height * 4
    font = ImageFont.truetype(font_path, font_size)
    height = max(font.getsize(c)[1] for c in CHARS)+b
    for c in CHARS:
        width = font.getsize(c)[0]
        im = Image.new('RGB', (width, height), (0, 0, 0))

        draw = ImageDraw.Draw(im)
        draw.text((0, 0), c, font_color,font=font)
        scale = float(output_height) / (height-b)
        im = im.resize((int(width * scale), output_height), Image.ANTIALIAS)       
        yield c, numpy.array(im).astype(numpy.float32) / 255.

def euler_to_mat(yaw, pitch, roll):

    # Rotate clockwise about the Y-axis
    c, s = math.cos(yaw), math.sin(yaw)
    M = numpy.matrix([[  c, 0.,  s],
                      [ 0., 1., 0.],
                      [ -s, 0.,  c]])

    # Rotate clockwise about the X-axis
    c, s = math.cos(pitch), math.sin(pitch)
    M = numpy.matrix([[ 1., 0., 0.],
                      [ 0.,  c, -s],
                      [ 0.,  s,  c]]) * M

    # Rotate clockwise about the Z-axis
    c, s = math.cos(roll), math.sin(roll)
    M = numpy.matrix([[  c, -s, 0.],
                      [  s,  c, 0.],
                      [ 0., 0., 1.]]) * M

    return M

def pick_colors():
    
    text_color = 1.
    
    return text_color

def make_affine_transform(from_shape, to_shape, 
                          min_scale, max_scale,
                          scale_variation=1.0,
                          rotation_variation=1.0,
                          translation_variation=1.0): 
						  
    out_of_bounds_scale = True
    out_of_bounds_trans = True
    from_size = numpy.array([[from_shape[1], from_shape[0]]]).T
    to_size = numpy.array([[to_shape[1], to_shape[0]]]).T

    while out_of_bounds_scale:
        scale = random.uniform((min_scale + max_scale) * 0.5 -
                               (max_scale - min_scale) * 0.5 * scale_variation,
                               (min_scale + max_scale) * 0.5 +
                               (max_scale - min_scale) * 0.5 * scale_variation)
        if scale > max_scale or scale < min_scale:
            continue
        out_of_bounds_scale = False
        
    roll = random.uniform(-0.3, 0.3) * rotation_variation
    pitch = random.uniform(-0.2, 0.2) * rotation_variation
    yaw = random.uniform(-1.2, 1.2) * rotation_variation
    M = euler_to_mat(yaw, pitch, roll)[:2, :2]
    h, w = from_shape[0], from_shape[1]
    corners = numpy.matrix([[-w, +w, -w, +w],
                            [-h, -h, +h, +h]]) * 0.5
    skewed_size = numpy.array(numpy.max(numpy.dot(M, corners), axis=1) -
                              numpy.min(numpy.dot(M, corners), axis=1))
    # Set the scale as large as possible such that the skewed and scaled shape
    # is less than or equal to the desired ratio in either dimension.
    scale *= numpy.min(to_size / skewed_size)
    # Set the translation such that the skewed and scaled image falls within
    # the output shape's bounds.
    while out_of_bounds_trans:
        trans = (numpy.random.random((2,1)) - 0.5) * translation_variation
        trans = ((2.0 * trans) ** 5.0) / 2.0
        if numpy.any(trans < -0.5) or numpy.any(trans > 0.5):
            continue
        out_of_bounds_trans = False
    trans = (to_size - skewed_size * scale) * trans

    center_to = to_size / 2.
    center_from = from_size / 2.
    M = euler_to_mat(yaw, pitch, roll)[:2, :2]
    M *= scale
    T = trans + center_to - numpy.dot(M, center_from)
    M = numpy.hstack([M, T])
    return M


def generate_code():
    
    code = CHARS
        
    return code

def generate_text(font_height, char_ims):

    h_padding = random.uniform(0.2, 0.4) * font_height
    v_padding = random.uniform(0.1, 0.3) * font_height
    spacing = font_height * random.uniform(-0.05, 0.05)
    radius = 1 + int(font_height * 0.1 * random.random())

    code = generate_code()
    text_width = sum(char_ims[c].shape[1] for c in code)
    text_width += (len(code) - 1) * spacing

    out_shape = (int(font_height + v_padding * 2),
                 int(text_width + h_padding * 2), 3)
				 
    text_color = pick_colors() 
    text_mask = numpy.zeros(out_shape)

    x = h_padding
    y = v_padding 
    for c in code:
        char_im = char_ims[c]
        ix, iy = int(x), int(y)
        text_mask[iy:iy + char_im.shape[0], ix:ix + char_im.shape[1], :] = char_im
        x += char_im.shape[1] + spacing
    
    text = numpy.ones(out_shape) * text_color * text_mask
    return text,text_mask,code


def generate_bg(images_dir):

    while True:
        filenames = os.listdir(images_dir)
        lines = len(filenames)
        randline = random.randint(0,lines)
        loadlist = []
        for i in range(0,opt.sumnumber):
            loadlist.append(filenames[random.randint(0,(lines-1))])
        for fn in loadlist:
            fullfilename = os.path.join(images_dir,fn)
            bg = cv2.imread(fullfilename, cv2.IMREAD_COLOR)
            bg = bg / 255.
            yield bg

def get_dominant_color(image):

    cv2.imwrite('1.jpg',image)
    image = Image.open('1.jpg').convert('RGBA')
    max_score = 0.0
    dominant_color = None
    for count, (r, g, b, a) in image.getcolors(image.size[0] * image.size[1]):
        if a == 0:
            continue
        saturation = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)[1]
        y = min(abs(r * 2104 + g * 4130 + b * 802 + 4096 + 131072) >> 13, 235)       
        y = (y - 16.0) / (235 - 16) 
           
        if y > 0.9:
            dominant_color = (r, g, b)
            continue

        score = (saturation + 0.1) * count
        
        if score > max_score:
            max_score = score
            dominant_color = (r, g, b)            
    os.remove(os.path.join('1.jpg')) 
    return dominant_color
	
def hsv2rgb(h, s, v):

    h = float(h)
    s = float(s)
    v = float(v)
    h60 = h / 60.0
    h60f = math.floor(h60)
    hi = int(h60f) % 6
    f = h60 - h60f
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r, g, b = 0, 0, 0
    if hi == 0: r, g, b = v, t, p
    elif hi == 1: r, g, b = q, v, p
    elif hi == 2: r, g, b = p, v, t
    elif hi == 3: r, g, b = p, q, v
    elif hi == 4: r, g, b = t, p, v
    elif hi == 5: r, g, b = v, p, q
    r, g, b = int(r * 255), int(g * 255), int(b * 255)
    return r, g, b

def rgb2hsv(r, g, b):

    r, g, b = r/255.0, g/255.0, b/255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx-mn
    if mx == mn:
        h = 0
    elif mx == r:
        h = (60 * ((g-b)/df) + 360) % 360
    elif mx == g:
        h = (60 * ((b-r)/df) + 120) % 360
    elif mx == b:
        h = (60 * ((r-g)/df) + 240) % 360
    if mx == 0:
        s = 0
    else:
        s = df/mx
    v = mx
    return h, s, v

def colorRGB(img_color):

    r = img_color[0]
    g = img_color[1]
    b = img_color[2]
    (h,s,v) = rgb2hsv(r, g, b)
    h = h + 90
    if h > 180:
        h = h - 180
    v = 1.0 - v  
    (r,g,b) = hsv2rgb(h, s, v)
    font_color = (r,g,b)
    return font_color
    
def generate_im(num_bg_images):

    bg = next(bgs)
    img_bg = bg * 255.
    bg_color = get_dominant_color(img_bg)
    font_color = colorRGB(bg_color)
    if font_color == (0,0,0):
        font_color = (1,1,1)
    fonts, font_char_ims= load_fonts(FONT_DIR, font_color)
    char_ims = font_char_ims[random.choice(fonts)]
    text, text_mask, code = generate_text(FONT_HEIGHT, char_ims)
    if len(code) < 5:
        M = make_affine_transform(
                from_shape=text.shape,
                to_shape=bg.shape,
                min_scale=0.2,
                max_scale=0.6,
                rotation_variation=0.6,
                scale_variation=1.2,
                translation_variation=0.6)
    else:
        M = make_affine_transform(
                from_shape=text.shape,
                to_shape=bg.shape,
                min_scale=0.5,
                max_scale=0.5,
                rotation_variation=0.1,
                scale_variation=0.2,
                translation_variation=0.2)
    ht, wt = text.shape[0], text.shape[1]

    corners_bf = numpy.matrix([[0, wt, 0, wt],
                               [0, 0, ht, ht]])
    text = cv2.warpAffine(text, M, (bg.shape[1], bg.shape[0]))
    corners_af = numpy.dot(M[:2, :2], corners_bf) + M[:2, -1]
    tl = numpy.min(corners_af, axis=1).T
    br = numpy.max(corners_af, axis=1).T
    box = numpy.hstack([tl, br])

    rand = 230
    (h,s,v) = rgb2hsv(bg_color[0],bg_color[1],bg_color[2])
    if v > 0.85 and v <= 1.0:
        out = bg -text*rand
        out[out<0] = 0
    else:
        out = text + bg
    out = cv2.resize(out, (bg.shape[1], bg.shape[0]))
    out = numpy.clip(out, 0., 1.)
    return out, code, box


def load_fonts(folder_path,font_color):

    font_char_ims = {}
    fonts = [f for f in os.listdir(folder_path) if f.endswith('.ttf')]
    for font in fonts:
        font_char_ims[font] = dict(make_char_ims(os.path.join(folder_path,
                                                              font),
                                                 FONT_HEIGHT,font_color))
    return fonts, font_char_ims


def generate_ims():
    '''
    Generate number plate images.

    :return:
        Iterable of number plate images.

    '''
    variation = 1.0

    while True:
        yield generate_im(num_bg_images)
    

if __name__ == '__main__':

    Wfile = open(WORD_TXT,'r')
    point_load = 'point.txt'
    count = -1
    cnt = 0
    if not os.path.exists(point_load):
        filena = Wfile
        Train_file = open(train_lable, 'w')
        Test_file = open(test_lable, 'w')
    else:
        Train_file = open(train_lable, 'a')
        Test_file = open(test_lable, 'a')
        try:
            assert os.path.getsize(point_load) != 0
        except:
            print ("the point file is None!!!")
            #return False
            sys.exit(0)
        point_file = open(point_load,'rb+')
        point = str(point_file.read())
        #print point
        cnt = int(point.split('_')[3].split('.')[0])+1
        point = point.split()[1]
        #print 'cnt = :',cnt
        for count,orgline in enumerate(Wfile):
            count += 1
            orgline=orgline.strip('\n')
            if orgline == point:                
                break
        linecache.clearcache()		
        filena = linecache.getlines(WORD_TXT)[count:]             
    if filena == []:
        print( "all datasets complete!!!")

    fname = BGS_DIR 
    filenames = os.listdir(BGS_DIR)
    for fn in filenames:
        fullfilename = os.path.join(BGS_DIR,fn)
        bg = cv2.imread(fullfilename, cv2.IMREAD_COLOR)
        imgH = 500
        h, w = bg.shape[:2]
        ratio = w / float(h)
        imgW = int(ratio * imgH)
        res=cv2.resize(bg,(imgW,imgH),interpolation = cv2.INTER_CUBIC)
        cv2.imwrite(fullfilename, res)

    num_bg_images = opt.sumnumber
    bgs = generate_bg(BGS_DIR)
    
    for line in filena:
        CHARS = line.strip('\n')
        im_gen = itertools.islice(generate_ims(), num_bg_images)
        for img_idx, (im, c, bx) in enumerate(im_gen):
            im = im * 255.
            rimage ='{0}_{1:08d}.png'.format(opt.str,cnt)
            print (rimage)
            crop = im[int(bx[:, 1]):int(bx[:, 3]), int(bx[:, 0]):int(bx[:, 2]), ]
                      
            imgH = 32
            h, w = crop.shape[:2]
            ratio = w / float(h)
            imgW = int(ratio * imgH)
            res=cv2.resize(crop,(imgW,imgH),interpolation = cv2.INTER_CUBIC)
            print(type(R_OUTPUT_DIR))
            print(type(os.sep))
            print(type(rimage.encode('utf-8')))
            print(type(res))
            cv2.imwrite(R_OUTPUT_DIR+os.sep+str(rimage.encode('utf-8')), res)
            if img_idx % (opt.sumnumber) <= (opt.trainnum-1):
                Train_file.write(str(str(rimage.encode('utf-8')) + ' ' + str(c.encode('utf-8')) + '\n'))
                Train_file.flush()					
            else:
                Test_file.write(str(str(rimage.encode('utf-8')) + ' ' + str(c.encode('utf-8')) + '\n'))
                Test_file.flush()
            cnt += 1
            point_file = open('point.txt','w')
            #print c.encode('utf-8')
            point_file.write(str(str(rimage.encode('utf-8')) + ' ' + str(c.encode('utf-8'))))
            point_file.flush()
            point_file.close()
    Train_file.close()
    Test_file.close()
    
    Wfile.close()
