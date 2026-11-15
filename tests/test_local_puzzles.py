import unittest
from unittest.mock import patch

import cv2
import numpy as np

from ruin.browser.puzzle_images import composite_points, gap_x
from test_yidun import puzzle_images


class LocalPuzzleTests(unittest.TestCase):
    def test_opencv_without_ocr_match(self):
        with patch('ruin.browser.puzzle_images.slide_engine', side_effect=RuntimeError('unavailable')):
            self.assertAlmostEqual(gap_x(*puzzle_images()), 182, delta=2)
            self.assertIsNone(gap_x(*puzzle_images(second_gap=True)))

    def test_flattened_contours_and_ambiguous_pair(self):
        bg, tile = puzzle_images()
        board = cv2.imdecode(np.frombuffer(bg, np.uint8), cv2.IMREAD_GRAYSCALE)
        fg = cv2.imdecode(np.frombuffer(tile, np.uint8), cv2.IMREAD_UNCHANGED)
        board[:, :96][fg[:, :, 3] > 0] = 90
        encode = lambda a: cv2.imencode('.png', a)[1].tobytes()
        points = composite_points(encode(board))
        self.assertIsNotNone(points)
        self.assertAlmostEqual((points['hole']-points['piece'])*480, 182, delta=2)
        board[:, 310:406][fg[:, :, 3] > 0] = 90
        self.assertIsNone(composite_points(encode(board)))

    def test_invalid_image(self):
        self.assertIsNone(composite_points(b'not an image'))
