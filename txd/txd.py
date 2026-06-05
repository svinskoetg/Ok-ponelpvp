from functools import lru_cache
import io
import zipfile
import random
import struct
import numpy as np
from PIL import Image
import logging
import shutil
import os
import asyncio
from typing import Optional
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BufferedInputFile
from aiogram.enums import ParseMode
from start.start import check_subscription

router = Router()
txd_converter = None

DOWNLOAD_FOLDER = "txd/txdfile"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

class TXDConverter:
    def __init__(self):
        self.output_dir = DOWNLOAD_FOLDER
        os.makedirs(self.output_dir, exist_ok=True)

    @lru_cache(maxsize=None)
    def unpack_color565(self, color):
        r = (color >> 11) & 0x1F
        g = (color >> 5) & 0x3F
        b = color & 0x1F
        return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255)

    @lru_cache(maxsize=None)
    def unpack_color5551(self, color):
        r = (color >> 11) & 0x1F
        g = (color >> 6) & 0x1F
        b = (color >> 1) & 0x1F
        a = (color & 0x1) * 255
        return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, a)

    @lru_cache(maxsize=None)
    def unpack_color4444(self, color):
        r = (color >> 12) & 0x0F
        g = (color >> 8) & 0x0F
        b = (color >> 4) & 0x0F
        a = color & 0x0F
        return (r << 4 | r, g << 4 | g, b << 4 | b, a << 4 | a)

    def decode_dxt1(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        blocks_wide = (width + 3) // 4
        blocks_high = (height + 3) // 4
        expected_size = blocks_wide * blocks_high * 8
        
        if len(data) < expected_size:
            data = data.ljust(expected_size, b'\x00')
        elif len(data) > expected_size:
            data = data[:expected_size]

        for block_y in range(blocks_high):
            for block_x in range(blocks_wide):
                offset = (block_y * blocks_wide + block_x) * 8
                if offset + 8 > len(data):
                    continue

                color0, color1 = struct.unpack('<HH', data[offset:offset+4])
                bits = struct.unpack('<I', data[offset+4:offset+8])[0]

                c0 = self.unpack_color565(color0)
                c1 = self.unpack_color565(color1)

                if color0 > color1:
                    c2 = ((2 * c0[0] + c1[0]) // 3, (2 * c0[1] + c1[1]) // 3, (2 * c0[2] + c1[2]) // 3, 255)
                    c3 = ((c0[0] + 2 * c1[0]) // 3, (c0[1] + 2 * c1[1]) // 3, (c0[2] + 2 * c1[2]) // 3, 255)
                else:
                    c2 = ((c0[0] + c1[0]) // 2, (c0[1] + c1[1]) // 2, (c0[2] + c1[2]) // 2, 255)
                    c3 = (0, 0, 0, 255)

                colors = np.array([c0, c1, c2, c3], dtype=np.uint8)

                for y in range(4):
                    for x in range(4):
                        px = min(block_x * 4 + x, width - 1)
                        py = min(block_y * 4 + y, height - 1)
                        bit_pos = 2 * (y * 4 + x)
                        color_idx = (bits >> bit_pos) & 0x03
                        img[py, px] = colors[color_idx]

        return Image.fromarray(img, 'RGBA')

    def decode_dxt3(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        blocks_wide = (width + 3) // 4
        blocks_high = (height + 3) // 4
        expected_size = blocks_wide * blocks_high * 16
        
        if len(data) < expected_size:
            data = data.ljust(expected_size, b'\x00')
        elif len(data) > expected_size:
            data = data[:expected_size]

        for block_y in range(blocks_high):
            for block_x in range(blocks_wide):
                offset = (block_y * blocks_wide + block_x) * 16
                if offset + 16 > len(data):
                    continue

                alpha_values = []
                for i in range(0, 8, 2):
                    alpha_byte1 = data[offset + i]
                    alpha_byte2 = data[offset + i + 1]
                    alpha_values.extend([
                        (alpha_byte1 & 0x0F) * 17,
                        (alpha_byte1 >> 4) * 17,
                        (alpha_byte2 & 0x0F) * 17,
                        (alpha_byte2 >> 4) * 17
                    ])
                alpha_values = np.array(alpha_values, dtype=np.uint8)

                color0, color1 = struct.unpack('<HH', data[offset + 8:offset + 12])
                bits = struct.unpack('<I', data[offset + 12:offset + 16])[0]

                c0 = self.unpack_color565(color0)
                c1 = self.unpack_color565(color1)

                if color0 > color1:
                    c2 = ((2 * c0[0] + c1[0]) // 3, (2 * c0[1] + c1[1]) // 3, (2 * c0[2] + c1[2]) // 3, 255)
                    c3 = ((c0[0] + 2 * c1[0]) // 3, (c0[1] + 2 * c1[1]) // 3, (c0[2] + 2 * c1[2]) // 3, 255)
                else:
                    c2 = ((c0[0] + c1[0]) // 2, (c0[1] + c1[1]) // 2, (c0[2] + c1[2]) // 2, 255)
                    c3 = (0, 0, 0, 255)

                colors = np.array([c0, c1, c2, c3], dtype=np.uint8)

                for y in range(4):
                    for x in range(4):
                        px = min(block_x * 4 + x, width - 1)
                        py = min(block_y * 4 + y, height - 1)
                        alpha_idx = y * 4 + x
                        a = alpha_values[alpha_idx]
                        bit_pos = 2 * (y * 4 + x)
                        color_idx = (bits >> bit_pos) & 0x03
                        r, g, b, _ = colors[color_idx]
                        img[py, px] = (r, g, b, a)

        return Image.fromarray(img, 'RGBA')

    def decode_dxt5(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        blocks_wide = (width + 3) // 4
        blocks_high = (height + 3) // 4
        expected_size = blocks_wide * blocks_high * 16
        
        if len(data) < expected_size:
            data = data.ljust(expected_size, b'\x00')
        elif len(data) > expected_size:
            data = data[:expected_size]

        for block_y in range(blocks_high):
            for block_x in range(blocks_wide):
                offset = (block_y * blocks_wide + block_x) * 16
                if offset + 16 > len(data):
                    continue

                alpha0 = data[offset]
                alpha1 = data[offset + 1]
                alpha_bits = data[offset + 2:offset + 8]

                alphas = [alpha0, alpha1]
                if alpha0 > alpha1:
                    alphas.extend([
                        (6 * alpha0 + 1 * alpha1) // 7,
                        (5 * alpha0 + 2 * alpha1) // 7,
                        (4 * alpha0 + 3 * alpha1) // 7,
                        (3 * alpha0 + 4 * alpha1) // 7,
                        (2 * alpha0 + 5 * alpha1) // 7,
                        (1 * alpha0 + 6 * alpha1) // 7
                    ])
                else:
                    alphas.extend([
                        (4 * alpha0 + 1 * alpha1) // 5,
                        (3 * alpha0 + 2 * alpha1) // 5,
                        (2 * alpha0 + 3 * alpha1) // 5,
                        (1 * alpha0 + 4 * alpha1) // 5,
                        0, 255
                    ])
                alphas = np.array(alphas, dtype=np.uint8)

                color0, color1 = struct.unpack('<HH', data[offset + 8:offset + 12])
                bits = struct.unpack('<I', data[offset + 12:offset + 16])[0]

                c0 = self.unpack_color565(color0)
                c1 = self.unpack_color565(color1)

                if color0 > color1:
                    c2 = ((2 * c0[0] + c1[0]) // 3, (2 * c0[1] + c1[1]) // 3, (2 * c0[2] + c1[2]) // 3, 255)
                    c3 = ((c0[0] + 2 * c1[0]) // 3, (c0[1] + 2 * c1[1]) // 3, (c0[2] + 2 * c1[2]) // 3, 255)
                else:
                    c2 = ((c0[0] + c1[0]) // 2, (c0[1] + c1[1]) // 2, (c0[2] + c1[2]) // 2, 255)
                    c3 = (0, 0, 0, 255)

                colors = np.array([c0, c1, c2, c3], dtype=np.uint8)

                for y in range(4):
                    for x in range(4):
                        px = min(block_x * 4 + x, width - 1)
                        py = min(block_y * 4 + y, height - 1)
                        alpha_pos = 3 * (y * 4 + x)
                        alpha_byte = alpha_pos // 8
                        alpha_shift = alpha_pos % 8
                        alpha_idx = (alpha_bits[alpha_byte] >> alpha_shift) & 0x07
                        if alpha_shift > 5 and alpha_byte + 1 < len(alpha_bits):
                            alpha_idx |= (alpha_bits[alpha_byte + 1] << (8 - alpha_shift)) & 0x07
                        bit_pos = 2 * (y * 4 + x)
                        color_idx = (bits >> bit_pos) & 0x03
                        r, g, b, _ = colors[color_idx]
                        a = alphas[alpha_idx]
                        img[py, px] = (r, g, b, a)

        return Image.fromarray(img, 'RGBA')

    def decode_bgr888(self, data, width, height):
        try:
            expected_size = width * height * 3
            if len(data) < expected_size:
                data += bytes(expected_size - len(data))
            elif len(data) > expected_size:
                data = data[:expected_size]

            arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
            rgba = np.zeros((height, width, 4), dtype=np.uint8)
            rgba[:, :, 0] = arr[:, :, 2]
            rgba[:, :, 1] = arr[:, :, 1]
            rgba[:, :, 2] = arr[:, :, 0]
            rgba[:, :, 3] = 255

            is_black = (arr[:, :, 0] == 0) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 0)
            rgba[is_black, 3] = 0

            return Image.fromarray(rgba, 'RGBA')
        except Exception as e:
            logging.error(f"ошибко декодирования BGR888: {e}")
            return Image.new('RGBA', (width, height), (0, 0, 0, 255))

    def decode_bgra8888(self, data, width, height):
        try:
            expected_size = width * height * 4
            if len(data) != expected_size:
                raise ValueError(f"некорректный размер данных BGRA8888. Ожидалось {expected_size}, получено {len(data)}")

            arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
            rgba = np.empty((height, width, 4), dtype=np.uint8)
            rgba[:, :, 0] = arr[:, :, 2]
            rgba[:, :, 1] = arr[:, :, 1]
            rgba[:, :, 2] = arr[:, :, 0]
            rgba[:, :, 3] = arr[:, :, 3]

            return Image.fromarray(rgba, 'RGBA')
        except Exception as e:
            logging.error(f"BGRA8888 decode error: {e}")
            return Image.new('RGBA', (width, height), (0, 0, 0, 255))

    def decode_argb1555(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                offset = (y * width + x) * 2
                if offset + 2 > len(data):
                    continue
                pixel = struct.unpack('<H', data[offset:offset+2])[0]
                img[y, x] = self.unpack_color5551(pixel)
        return Image.fromarray(img, 'RGBA')

    def decode_rgba4444(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                offset = (y * width + x) * 2
                if offset + 2 > len(data):
                    continue
                pixel = struct.unpack('<H', data[offset:offset+2])[0]
                img[y, x] = self.unpack_color4444(pixel)
        return Image.fromarray(img, 'RGBA')

    def decode_bgra(self, data, width, height):
        expected_size = width * height * 4
        if len(data) < expected_size:
            data = data.ljust(expected_size, b'\x00')
        elif len(data) > expected_size:
            data = data[:expected_size]
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        rgba = np.empty((height, width, 4), dtype=np.uint8)
        rgba[:, :, 0] = arr[:, :, 2]
        rgba[:, :, 1] = arr[:, :, 1]
        rgba[:, :, 2] = arr[:, :, 0]
        rgba[:, :, 3] = arr[:, :, 3]
        return Image.fromarray(rgba, 'RGBA')

    def decode_abgr8888(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        arr = arr[:, :, [3, 2, 1, 0]]
        return Image.fromarray(arr, 'RGBA')

    def decode_argb8888(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        arr = arr[:, :, [1, 2, 3, 0]]
        return Image.fromarray(arr, 'RGBA')

    def decode_bgr565(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                offset = (y * width + x) * 2
                if offset + 2 > len(data):
                    continue
                pixel = struct.unpack('<H', data[offset:offset+2])[0]
                b = (pixel >> 11) & 0x1F
                g = (pixel >> 5) & 0x3F
                r = pixel & 0x1F
                img[y, x] = (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255)
        return Image.fromarray(img, 'RGBA')

    def decode_bgr888_bluescreen(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
        arr = arr[:, :, [2, 1, 0]]
        img = Image.fromarray(arr, 'RGB')
        
        img = img.convert('RGBA')
        data = np.array(img)
        r, g, b, a = data.T
        bluescreen_areas = (r == 0) & (g == 0) & (b == 255)
        a[bluescreen_areas] = 0
        data = np.array([r, g, b, a]).T
        
        return Image.fromarray(data, 'RGBA')

    def decode_bgra4444(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                offset = (y * width + x) * 2
                if offset + 2 > len(data):
                    continue
                pixel = struct.unpack('<H', data[offset:offset+2])[0]
                b = (pixel >> 12) & 0x0F
                g = (pixel >> 8) & 0x0F
                r = (pixel >> 4) & 0x0F
                a = pixel & 0x0F
                img[y, x] = (r << 4 | r, g << 4 | g, b << 4 | b, a << 4 | a)
        return Image.fromarray(img, 'RGBA')

    def decode_bgra5551(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                offset = (y * width + x) * 2
                if offset + 2 > len(data):
                    continue
                pixel = struct.unpack('<H', data[offset:offset+2])[0]
                b = (pixel >> 11) & 0x1F
                g = (pixel >> 6) & 0x1F
                r = (pixel >> 1) & 0x1F
                a = (pixel & 0x1) * 255
                img[y, x] = (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, a)
        return Image.fromarray(img, 'RGBA')

    def decode_rgb8888(self, data, width, height):
        expected_size = width * height * 4
        if len(data) < expected_size:
            data = data.ljust(expected_size, b'\x00')
        elif len(data) > expected_size:
            data = data[:expected_size]
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        rgba = np.empty((height, width, 4), dtype=np.uint8)
        rgba[:, :, 0] = arr[:, :, 2]
        rgba[:, :, 1] = arr[:, :, 1]
        rgba[:, :, 2] = arr[:, :, 0]
        rgba[:, :, 3] = arr[:, :, 3]
        alpha_channel = rgba[:, :, 3]
        alpha_mean = np.mean(alpha_channel)
        alpha_std = np.std(alpha_channel)
        if alpha_mean < 50 and alpha_std < 30:
            rgba[:, :, 3] = 255 - rgba[:, :, 3]
        elif alpha_mean < 10:
            rgba[:, :, 3] = 255
        return Image.fromarray(rgba, 'RGBA')

    def decode_bgrx5551(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                offset = (y * width + x) * 2
                if offset + 2 > len(data):
                    continue
                pixel = struct.unpack('<H', data[offset:offset+2])[0]
                b = (pixel >> 11) & 0x1F
                g = (pixel >> 6) & 0x1F
                r = (pixel >> 1) & 0x1F
                img[y, x] = (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, 255)
        return Image.fromarray(img, 'RGBA')

    def decode_bgrx8888(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        arr = arr[:, :, [2, 1, 0]]
        alpha = np.full((height, width, 1), 255, dtype=np.uint8)
        arr = np.concatenate((arr[:, :, :3], alpha), axis=2)
        return Image.fromarray(arr, 'RGBA')

    def decode_i8(self, data, width, height):
        img = Image.frombytes('L', (width, height), bytes(data))
        return img.convert('RGBA')

    def decode_ia88(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 2))
        img = np.zeros((height, width, 4), dtype=np.uint8)
        img[:, :, 0] = arr[:, :, 0]
        img[:, :, 1] = arr[:, :, 0]
        img[:, :, 2] = arr[:, :, 0]
        img[:, :, 3] = arr[:, :, 1]
        return Image.fromarray(img, 'RGBA')

    def decode_rgb565(self, data, width, height):
        img = np.zeros((height, width, 4), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                offset = (y * width + x) * 2
                if offset + 2 > len(data):
                    continue
                pixel = struct.unpack('<H', data[offset:offset+2])[0]
                r = (pixel >> 11) & 0x1F
                g = (pixel >> 5) & 0x3F
                b = pixel & 0x1F
                img[y, x] = (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255)
        return Image.fromarray(img, 'RGBA')

    def decode_rgb888_bluescreen(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3))
        img = Image.fromarray(arr, 'RGB')
        
        img = img.convert('RGBA')
        data = np.array(img)
        r, g, b, a = data.T
        bluescreen_areas = (r == 0) & (g == 0) & (b == 255)
        a[bluescreen_areas] = 0
        data = np.array([r, g, b, a]).T
        
        return Image.fromarray(data, 'RGBA')

    def decode_rgbah6161616(self, data, width, height):
        arr = np.frombuffer(data, dtype='<u2').reshape((height, width, 4))
        arr = arr.astype(np.float32) / 65535.0 * 255.0
        arr = arr.astype(np.uint8)
        return Image.fromarray(arr, 'RGBA')

    def decode_rgbah6161616f(self, data, width, height):
        arr = np.frombuffer(data, dtype='<f2').reshape((height, width, 4))
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(arr, 'RGBA')

    def decode_uv88(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 2))
        img = np.zeros((height, width, 4), dtype=np.uint8)
        img[:, :, 0] = arr[:, :, 0]
        img[:, :, 1] = arr[:, :, 1]
        img[:, :, 2] = 128
        img[:, :, 3] = 255
        return Image.fromarray(img, 'RGBA')

    def decode_uvlx8888(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        img = np.zeros((height, width, 4), dtype=np.uint8)
        img[:, :, 0] = arr[:, :, 0]
        img[:, :, 1] = arr[:, :, 1]
        img[:, :, 2] = arr[:, :, 2]
        img[:, :, 3] = arr[:, :, 3]
        return Image.fromarray(img, 'RGBA')

    def decode_uvwq8888(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
        img = np.zeros((height, width, 4), dtype=np.uint8)
        img[:, :, 0] = arr[:, :, 0]
        img[:, :, 1] = arr[:, :, 1]
        img[:, :, 2] = arr[:, :, 2]
        img[:, :, 3] = arr[:, :, 3]
        return Image.fromarray(img, 'RGBA')

    def decode_ab(self, data, width, height):
        arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 1))
        img = np.zeros((height, width, 4), dtype=np.uint8)
        img[:, :, 3] = arr[:, :, 0]
        return Image.fromarray(img, 'RGBA')

    def parseXBytes(self, data: bytes, start: int, byte_count: int, raw: bool = False):
        if not raw:
            n = int.from_bytes(data[start: start + byte_count], "little")
        else:
            n = data[start: start + byte_count]
        start += byte_count
        return n, start

    def parseMipMaps(self, data: bytes, start: int, mipmap_count: int):
        mipmap_bin = b''
        for _ in range(mipmap_count - 1):
            data_size, start = self.parseXBytes(data, start, 4)
            mipmap_bin += data[start: start + data_size]
            start += data_size
        return mipmap_bin, start

    def decode_texture_to_image(self, texture_data, name_counter=None):
        width = texture_data['width']
        height = texture_data['height']
        depth = texture_data['depth']
        palette = texture_data.get('palette')
        data = texture_data['data']
        name = texture_data["name"]
        d3d_format_raw = texture_data.get('direct3d_texture_format', b'')
        d3d_format = d3d_format_raw.decode('utf-8', 'ignore').strip()

        try:
            if d3d_format == 'DXT1':
                img = self.decode_dxt1(data, width, height)
            elif d3d_format == 'DXT3':
                img = self.decode_dxt3(data, width, height)
            elif d3d_format == 'DXT5':
                img = self.decode_dxt5(data, width, height)
            elif d3d_format == 'ABGR8888':
                img = self.decode_abgr8888(data, width, height)
            elif d3d_format == 'ARGB8888':
                img = self.decode_argb8888(data, width, height)
            elif d3d_format == 'BGR565':
                img = self.decode_bgr565(data, width, height)
            elif d3d_format == 'BGR888':
                img = self.decode_bgr888(data, width, height)
            elif d3d_format == 'BGR888_BLUESCREEN':
                img = self.decode_bgr888_bluescreen(data, width, height)
            elif d3d_format == 'BGRA4444':
                img = self.decode_bgra4444(data, width, height)
            elif d3d_format == 'BGRA5551':
                img = self.decode_bgra5551(data, width, height)
            elif d3d_format == 'BGRA8888' or d3d_format == 'BGRA':
                img = self.decode_bgra(data, width, height)
            elif d3d_format == 'BGRX5551':
                img = self.decode_bgrx5551(data, width, height)
            elif d3d_format == 'BGRX8888':
                img = self.decode_bgrx8888(data, width, height)
            elif d3d_format == 'I8':
                img = self.decode_i8(data, width, height)
            elif d3d_format == 'IA88':
                img = self.decode_ia88(data, width, height)
            elif d3d_format == 'RGB565':
                img = self.decode_rgb565(data, width, height)
            elif d3d_format == 'RGB888':
                img = Image.frombytes('RGB', (width, height), bytes(data)).convert('RGBA')
            elif d3d_format == 'RGB888_BLUESCREEN':
                img = self.decode_rgb888_bluescreen(data, width, height)
            elif d3d_format == 'RGBAH6161616':
                img = self.decode_rgbah6161616(data, width, height)
            elif d3d_format == 'RGBAH6161616F':
                img = self.decode_rgbah6161616f(data, width, height)
            elif d3d_format == 'RGBA8888' or (d3d_format == 'RGBA' and depth == 32):
                img = self.decode_rgb8888(data, width, height)
            elif d3d_format == 'UV88':
                img = self.decode_uv88(data, width, height)
            elif d3d_format == 'UVLX8888':
                img = self.decode_uvlx8888(data, width, height)
            elif d3d_format == 'UVWQ8888':
                img = self.decode_uvwq8888(data, width, height)
            elif d3d_format == 'AB':
                img = self.decode_ab(data, width, height)
            elif d3d_format == 'ARGB1555' or (d3d_format == 'ARGB' and depth == 16):
                img = self.decode_argb1555(data, width, height)
            elif d3d_format == 'RGBA4444' or (d3d_format == 'RGBA' and depth == 16):
                img = self.decode_rgba4444(data, width, height)
            elif len(d3d_format) == 4:
                char_codes = [ord(c) for c in d3d_format]
                if char_codes[0] in [21, 22] and all(c == 0 for c in char_codes[1:]):
                    expected_size = width * height * 4
                    if len(data) < expected_size:
                        data = data.ljust(expected_size, b'\x00')
                    elif len(data) > expected_size:
                        data = data[:expected_size]
                    arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 4))
                    rgba = np.empty((height, width, 4), dtype=np.uint8)
                    rgba[:, :, 0] = arr[:, :, 2]
                    rgba[:, :, 1] = arr[:, :, 1]
                    rgba[:, :, 2] = arr[:, :, 0]
                    rgba[:, :, 3] = arr[:, :, 3]
                    alpha_channel = rgba[:, :, 3]
                    alpha_mean = np.mean(alpha_channel)
                    alpha_std = np.std(alpha_channel)
                    if alpha_mean < 50 and alpha_std < 30:
                        rgba[:, :, 3] = 255 - rgba[:, :, 3]
                    elif alpha_mean < 10:
                        rgba[:, :, 3] = 255
                    img = Image.fromarray(rgba, 'RGBA')
                else:
                    raise ValueError(f"Unsupported custom format: {d3d_format}")
            elif depth == 8 and palette:
                palette_bytes = bytes(palette)
                img = Image.frombytes('P', (width, height), bytes(data))
                img.putpalette(palette_bytes[:256 * 3])
                img = img.convert('RGBA')
            elif depth == 24:
                img = self.decode_bgr888(data, width, height)
            elif depth == 32:
                img = self.decode_bgra(data, width, height)
            else:
                if depth == 16:
                    img = self.decode_argb1555(data, width, height)
                elif depth == 24:
                    img = self.decode_bgr888(data, width, height)
                elif depth == 32:
                    img = self.decode_bgra(data, width, height)
                else:
                    raise ValueError(f"Unsupported depth/format combination: depth={depth}, format='{d3d_format}'")

            name = name.replace(" ", "_")
            if name_counter is not None:
                suffix = "_1" if name_counter.get(name, 0) > 0 else ""
                temp_filename = os.path.join(self.output_dir, f"{name}{suffix}.png")
            else:
                temp_filename = os.path.join(self.output_dir, f"{name}.png")
            img.save(temp_filename, "PNG", compress_level=1)
            return temp_filename
        except Exception as e:
            logging.error(f"Error decoding texture {name}: {e}")
            return None

    def parse_txd_data(self, data: bytes):
        i = 0
        byte_count = len(data)
        inside_texture = False
        png_files = []
        total_textures = 0
        processed_textures = 0
        name_counter = {}

        while i < byte_count:
            theid, i = self.parseXBytes(data, i, 4)
            chunk_size, i = self.parseXBytes(data, i, 4)
            rw_version, i = self.parseXBytes(data, i, 4)

            if theid == 22:
                pass
            elif theid == 1 and not inside_texture:
                total_textures = int.from_bytes(data[i:i+2], "little")
                i += 2
                i += 2
            elif theid == 1 and inside_texture:
                version, i = self.parseXBytes(data, i, 4)
                filter_flags, i = self.parseXBytes(data, i, 4)
                
                texture_name_bytes, i = self.parseXBytes(data, i, 32, True)
                texture_name = texture_name_bytes.split(b'\x00')[0].decode('latin-1')
                
                alpha_name_bytes, i = self.parseXBytes(data, i, 32, True)
                alpha_flags, i = self.parseXBytes(data, i, 4)
                
                direct3d_texture_format, i = self.parseXBytes(data, i, 4, True)
                
                width, i = self.parseXBytes(data, i, 2)
                height, i = self.parseXBytes(data, i, 2)
                depth, i = self.parseXBytes(data, i, 1)
                mipmap_count, i = self.parseXBytes(data, i, 1)
                texcode_type, i = self.parseXBytes(data, i, 1)
                flags, i = self.parseXBytes(data, i, 1)
                
                palette = None
                if depth == 8:
                    palette, i = self.parseXBytes(data, i, 1024, True)
                
                data_size, i = self.parseXBytes(data, i, 4)
                texture_data, i = self.parseXBytes(data, i, data_size, True)
                
                mipmaps, i = self.parseMipMaps(data, i, mipmap_count)

                texture_info = {
                    "name": texture_name,
                    "direct3d_texture_format": direct3d_texture_format,
                    "width": width,
                    "height": height,
                    "depth": depth,
                    "mipmap_count": mipmap_count,
                    "data_size": data_size,
                    "data_real_size": len(texture_data),
                    "palette": palette,
                    "data": texture_data
                }

                temp_png_path = self.decode_texture_to_image(texture_info, name_counter)
                if temp_png_path:
                    png_files.append(temp_png_path)

                name_counter[texture_name] = name_counter.get(texture_name, 0) + 1
                processed_textures += 1
                inside_texture = False

            elif theid == 21:
                inside_texture = True
            elif theid == 3:
                pass
            else:
                i += chunk_size - 4

        return png_files

    async def convert(self, file_data: io.BytesIO, filename: str) -> Optional[BufferedInputFile]:
        try:
            temp_dir = os.path.join(self.output_dir, f"temp_{random.randint(1000, 9999)}")
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                original_output_dir = self.output_dir
                self.output_dir = temp_dir
                
                file_bytes = file_data.getvalue()
                png_files = self.parse_txd_data(file_bytes)
                
                if not png_files:
                    return None
    
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for png_file in png_files:
                        zip_file.write(png_file, os.path.basename(png_file))
                
                zip_buffer.seek(0)
                return BufferedInputFile(
                    zip_buffer.getvalue(),
                    filename=f"{os.path.splitext(filename)[0]}.zip"
                )
            finally:
                self.output_dir = original_output_dir
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                
        except Exception as e:
            logging.error(f"TXD conversion error: {str(e)}", exc_info=True)
            return None

async def setup_txd_converter():
    global txd_converter
    txd_converter = TXDConverter()

@router.message(Command("txd"))
async def txd(message: types.Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
    name = message.from_user.first_name
    
    msg = await message.answer(
        f"<b>чтоб распаковать файл TXD в ZIP кидай файл - TXD</b>"
    )

@router.message(F.document & F.document.file_name.endswith('.txd'))
async def txd_xyina(message: types.Message, bot: Bot):
    if not await check_subscription(message, bot):
        return
        
    if message.caption and any(word.startswith('/') for word in message.caption.split()):
        return

    name = message.from_user.first_name
    
    global txd_converter
    if txd_converter is None:
        txd_converter = TXDConverter()
    
    progress_msg = await message.reply(f"<b>⏳ процесс идёт ок.</b>", parse_mode="HTML")
    
    try:
        file = await message.bot.get_file(message.document.file_id)

        file_data = io.BytesIO()
        await message.bot.download_file(file.file_path, destination=file_data)
        
        file_bytes = file_data.getvalue()
        png_files = txd_converter.parse_txd_data(file_bytes)
        
        if not png_files:
            await progress_msg.edit_text(f"<b>не удалось извлечь текстуры из файла</b>")
            return

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for png_file in png_files:
                zip_file.write(png_file, os.path.basename(png_file))
        
        zip_buffer.seek(0)
        result = BufferedInputFile(
            zip_buffer.getvalue(),
            filename=f"{os.path.splitext(message.document.file_name)[0]}.zip"
        )
            
        await message.reply_document(
            result,
            caption=f"<b>📊 файл готов</b>\n<b>📝 назва - {os.path.splitext(message.document.file_name)[0]}.zip</b>"
        )
    except Exception as e:
        logging.error(f"TXD processing error: {e}", exc_info=True)
        await progress_msg.edit_text(f"<b>❌ гондон, {name}! Произошла овер большая ошибко: {str(e)}</b>")
    finally:
        await asyncio.sleep(5)
        try:
            await progress_msg.delete()
        except:
            pass