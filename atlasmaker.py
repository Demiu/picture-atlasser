from __future__ import annotations
from dataclasses import dataclass
from typing import List, Union, Optional, Tuple
from PIL import Image, ImageColor
import argparse
import glob
import math
import os

verbose = False

# 2d bsp tree branch
# divides branch's space into two subrectangles with a (vertical or horizontal) line 
@dataclass
class Branch:
    # thing occupying the branch's space left (or up) of this branch's divisor
    left: Union[Branch, Image.Image, None] = None
    # thing occupying the branch's space right (or down) of this branch's divisor
    right: Union[Branch, Image.Image, None] = None
    # vertical or horizontal offset of this branch's divisor from the start (left top) of this branch
    offset: int = 0

# data for traversing our version of bsp tree iteratively
@dataclass
class BranchTraverseNode:
    # the branch associated with this traverse node
    branch: Optional[Branch] = None
    # TOTAL x offset of this subBranch, aka sum of all offsets of parent branches of branch with is_height false
    offsetx: int = 0
    # TOTAL y offset of this subBranch, aka sum of all offsets of parent branches of branch with is_height true
    offsety: int = 0
    # did we go left from this node?
    goes_left: bool = True

# inserts img into root tree, returns tree and either two zeroes if it inserted or smallest values of missing width and height
def insert_into_tree(root: Optional[Branch], maxw: int, maxh: int, img: Image.Image) -> Tuple[Optional[Branch], int, int]:
    # if this is the first insertion, it's a simple insertion
    if root == None:
        missingw = img.width - maxw
        missingh = img.height - maxh
        if missingw > 0 or missingh > 0:
            return None, missingw, missingh
        root = Branch()
        root.offset = img.height
        root.left = Branch()
        root.left.offset = img.width
        root.left.left = img
        return root, 0, 0

    # not first insertion, we need to traverse the tree
    # we start from the "right" of the root node 
    # because to reach this point the first image has to be already inserted
    traverse_stack = []
    traverse_stack.append(BranchTraverseNode(root, 0, 0, True))

    # smallest mising widths and heights
    missingw = 0
    missingh = 0

    while len(traverse_stack) > 0:
        previous_node = traverse_stack[-1]
        parent = previous_node.branch
        # this offsets don't actually represent the actual offset from top-right
        # but rather offset to a point, which together with maximum bottom-right point define
        # the equivalent rectange of parent's total size
        offsetx = previous_node.offsetx
        offsety = previous_node.offsety

        # is a branch that would be inserted dividing the space vertically (or horizontally if false) 
        # (NOT if it's dividing with a vertical plane)
        is_height = (len(traverse_stack) % 2) == 0

        dead_end = False

        # if goes_left is false we ignore the left branch
        if parent.left != None:
            if isinstance(parent.left, Branch) and previous_node.goes_left:
                # parent's left is a branch, descend into it
                # we add in parent's offset in reverse is_height because is_height reffers to us
                # using a little trick with maxes we make the behave the top-left calculations behave as if they were for bottom-right 
                new_offsetx = offsetx if not is_height else (maxw - parent.offset)
                new_offsety = offsety if     is_height else (maxh - parent.offset)
                traverse_stack.append(BranchTraverseNode(parent.left, new_offsetx, new_offsety, True))
                continue
            elif not isinstance(parent.left, Image.Image) and previous_node.goes_left:
                print("parent.left in bsp traversal is neither a Branch nor an Image, this should never happen")
            # else parent.left is an image
        else:
            print("Empty parent.left in bsp traversal, this should never happen")
        
        if parent.right != None:
            if isinstance(parent.right, Branch):
                # parent's right is a branch, descend into it
                # we add in parent's offset in reverse is_height because is_height reffers to us
                # change previous node
                previous_node.goes_left = False
                #previous_node.offsetx = offsetx if not is_height else (maxw - previous_node.offsetx)
                #previous_node.offsety = offsety if     is_height else (maxh - previous_node.offsety)
                new_offsetx = offsetx if not is_height else (offsetx + parent.offset)
                new_offsety = offsety if     is_height else (offsety + parent.offset)
                traverse_stack.append(BranchTraverseNode(parent.right, new_offsetx, new_offsety, True))
                continue
            elif not isinstance(parent.right, Image.Image):
                print("parent.right in bsp traversal is neither a Branch nor an Image, this should never happen")
            # else parent.right is an image
            dead_end = True

        # parent.right is null, try to fit our img into it
        our_height = maxh - offsety
        our_width  = maxw - offsetx
        if is_height:
            our_width -= parent.offset # parent was dividing width
        else:
            our_height -= parent.offset # parent was dividing height

        # check if we can even fit
        if (img.height > our_height or img.width > our_width) and not dead_end:
            # set the missing minimums, if there are new
            missingh = max(img.height - our_height, 0) if (missingh == 0) else min(missingh, max(img.height - our_height, 0))
            missingw = max(img.width - our_width, 0) if (missingw == 0) else min(missingw, max(img.width - our_width, 0))
            dead_end = True

        if dead_end:
            # now we go up, either popping branches where we went to right, or going into right branches where we went left
            # pop the current node, it's useless, if we reached this point we checked both left and right for it
            popped_node = traverse_stack.pop()
            while len(traverse_stack) > 1:
                # pop a new node, might be reinserted or discarded
                popped_node = traverse_stack.pop()
                popped_parent = traverse_stack[-1]
                # first try to go right if we previously went left at the parent (reinsertion)
                if popped_node.goes_left:
                    popped_node.goes_left = False

                    # fix the offset
                    new_is_height = (len(traverse_stack) % 2) == 0
                    popped_node.offsetx = popped_node.offsetx if not new_is_height else (popped_parent.offsetx + popped_parent.branch.offset)
                    popped_node.offsety = popped_node.offsety if     new_is_height else (popped_parent.offsety + popped_parent.branch.offset)
                    # and reinsert
                    traverse_stack.append(popped_node)
                    break
                # else we go further up, since we already checked right (and we always check left before right)
            
            # we went through the whole tree, reached the root
            if len(traverse_stack) == 1:
                if traverse_stack[0].goes_left:
                    traverse_stack[0].goes_left = False # now do the right branch of root
                else:
                    break # we did the left and the right of the root, the piece doesn't fit
            continue
            
        if img.height == our_height:
            if img.width == our_width:
                # perfect fit
                parent.right = img
                return root, 0, 0
            else:
                # perfect fit height, too much width
                if not is_height:
                    parent.right = Branch()
                    parent.right.offset = img.width
                    parent.right.left = img
                    return root, 0, 0
        else:
           if img.width == our_width:
                # perfect fit width, too much height
                if is_height:
                    parent.right = Branch()
                    parent.right.offset = img.height
                    parent.right.left = img
                    return root, 0, 0

        # both don't match  
        parent.right = Branch()
        parent.right.offset = img.height if is_height else img.width
        parent.right.left = Branch()
        parent.right.left.offset = img.width if is_height else img.height # reversed since it's a level down
        parent.right.left.left = img
        return root, 0, 0
    
    # we have reached the end of the tree, (maxw, maxh) sized rect cant fill this root and a new image

    # fix edge cases for missing widths (eg. a fully filled rect will have those still at 0)
    missingw = min(missingw, img.width) if missingw != 0 else img.width
    missingh = min(missingh, img.height) if missingh != 0 else img.height

    # return unchanged root and how much we're (approximately) missing in each direction
    return root, missingw, missingh

def guess_size(images: List[Image.Image], pow2: bool, sq: bool):
    # minimum widths and heights for the size (from maximums of images)
    minw = 0
    minh = 0
    total_px = 0

    for img in images:
        minw = img.width if minw == 0 else max(minw, img.width)
        minh = img.height if minh == 0 else max(minh, img.height)
        total_px += img.width * img.height
    
    if pow2:
        if sq:
            # square of power 2
            bigger = max(minh, minw) # we cant fit in smaller side, giess from bigger
            guess = 2 ** int(math.ceil(math.log2(bigger)))
            # expand until we can fit
            while (guess * guess) < total_px:
                guess *= 2
            # we expanded enough
            return guess, guess 
        else:
            # rect of power 2
            w = 2 ** int(math.ceil(math.log2(minw)))
            h = 2 ** int(math.ceil(math.log2(minh)))
            # expand until we can fit, proritizing smallest side
            while (w * h) < total_px:
                if w > h:
                    h *= 2
                else:
                    w *= 2
            return w, h
    else:
        if sq:
            # square
            # minimum side to fit all pixels and image width/height requirements, respectively
            from_total = int(math.ceil(math.sqrt(total_px)))
            from_mins = max(minw, minh)
            if from_mins > from_total:
                # if we'd use from_total sides would be too short
                return from_mins, from_mins
            else:
                return from_total, from_total
        else:
            # rect
            # simple minimums check
            if (minw * minh) >= total_px:
                return minw, minh
            
            squareish_side = int(math.ceil(math.sqrt(total_px)))
            if minw > minh:
                final_side = max(squareish_side, minw)
                return final_side, final_side
            else:
                final_side = max(squareish_side, minh)
                return final_side, final_side

def next_best_size(w: int, h: int, pow2: bool, sq: bool, missw: int, missh: int):
    if pow2:
        if sq:
            # square of power 2
            needed_powerw = int(math.ceil(math.log2(w + missw)))
            needed_powerh = int(math.ceil(math.log2(h + missh)))
            if needed_powerh > needed_powerw:
                return 2**needed_powerw, 2**needed_powerw
            else:
                return 2**needed_powerh, 2**needed_powerh
        else:
            # rect of power 2
            needed_powerw = int(math.ceil(math.log2(w + missw)))
            needed_powerh = int(math.ceil(math.log2(h + missh)))
            new_pixelsw = (2**needed_powerw) * h
            new_pixelsh = (2**needed_powerh) * w
            if new_pixelsw > new_pixelsh:
                return w, (2**needed_powerh)
            else:
                return (2**needed_powerw), h
    else:
        if sq:
            # square
            # how many new pixels will be created if we expand the width by missw, and vice-versa
            # the num of pixel isn't accurate, but they are correct for comparassions
            new_pixelsw = h * missw 
            new_pixelsh = w * missh
            if new_pixelsw > new_pixelsh:
                return w, (h + missh)
            elif new_pixelsw < new_pixelsh:
                return (w + missw), h
            else:
                if w > h:
                    return w, (h + missh)
                else:
                    return (w + missw), h 
        else:
            # just a rect
            new_pixelsw = missw * h
            new_pixelsh = missh * w
            if new_pixelsw > new_pixelsh:
                return w, (h + missh)
            elif new_pixelsw < new_pixelsh:
                return (w + missw), h
            else:
                if w > h:
                    return w, (h + missh)
                else:
                    return (w + missw), h

def generate_tree(images: List[Image.Image], pow2: bool, sq: bool):
    if verbose:
        print("Generating tree...")
    
    images.sort(key=lambda img: img.height)

    w, h = guess_size(images, pow2, sq)
    if verbose:
        print("Initial guess of a (%d, %d) rectangle" % (w, h))

    images_left = images.copy()
    tree = None
    while images_left:
        image = images_left.pop()
        tree, missx, missy = insert_into_tree(tree, w, h, image)
        if missx != 0 or missy != 0:
            w, h = next_best_size(w, h, pow2, sq, missx, missy)
            images_left = images.copy()
            tree = None
            if verbose:
                print("Rect too small by (%d, %d), expanded to (%d, %d)" % (missx, missy, w, h))

    if verbose:
        print("Done generating tree!")

    return tree, w, h

def tree_into_image(tree: Branch, width: int, height: int):
    dest = Image.new('RGBA', (width, height), ImageColor.getrgb('#00000000'))

    traverse_stack = []
    traverse_stack.append(BranchTraverseNode(tree, 0, 0, True))

    while len(traverse_stack) > 0:
        previous_node = traverse_stack[-1]
        parent = previous_node.branch
        offsetx = previous_node.offsetx
        offsety = previous_node.offsety
        is_height = (len(traverse_stack) % 2) == 0

        if parent.left != None and previous_node.goes_left:
            if isinstance(parent.left, Branch):
                # descend into it
                traverse_stack.append(BranchTraverseNode(parent.left, offsetx, offsety, True))
                continue
            elif isinstance(parent.left, Image.Image):
                dest.paste(parent.left, (offsetx, offsety))
                previous_node.goes_left = False # now check the right
                continue
            else:
                print("parent.left in bsp traversal is neither a Branch nor an Image, this should never happen")
        
        if parent.right != None:
            if isinstance(parent.right, Branch):
                # descend into it
                new_offsetx = offsetx if not is_height else (offsetx + parent.offset)
                new_offsety = offsety if     is_height else (offsety + parent.offset)
                traverse_stack.append(BranchTraverseNode(parent.right, new_offsetx, new_offsety, True))
                continue
            elif isinstance(parent.right, Image.Image):
                new_offsetx = offsetx if not is_height else (offsetx + parent.offset)
                new_offsety = offsety if     is_height else (offsety + parent.offset)
                dest.paste(parent.right, (new_offsetx, new_offsety))
                # we don't continue to fall into the upwards backtracking code
            else:
                print("parent.right in bsp traversal is neither a Branch nor an Image, this should never happen")

        # we either already went left, or can't got left nor right, so we go up until we find a branch left
        traverse_stack.pop() # current branch is handled
        while len(traverse_stack) > 0:
            popped_parent = traverse_stack[-1]
            if popped_parent.goes_left:
                # switch the popped_parent from left to right
                popped_parent.goes_left = False
                break
            elif len(traverse_stack) != 0:
                traverse_stack.pop() # further up
            else:
                break # both loops exit
    
    return dest

def load_file_list(files: List[str]):
    images = []
    for f in files:
        try:
            i = Image.open(f)
            images.append(i)
            print("Loaded %s" % f)
        except IOError:
            if verbose:
                print("Can't load %s, skipping..." % f) 
    return images

def load_directory(path: str):
    path = os.path.join(path, '*')
    files = glob.glob(path, recursive=True)
    return load_file_list(files)

def load_file(path: str):
    try:
        i = Image.open(path)
        print("Loaded %s" % path)
        return i
    except IOError:
        if verbose:
            print("Can't load %s, skipping..." % path)
    return None

def load(path: str):
    images = []

    if os.path.isdir(path):
        images.extend(load_directory(path))
    elif os.path.isfile(path):
        i = load_file(path)
        if i != None:
            images.append(i)
    else:
        paths = glob.glob(path)
        for p in paths:
            images.extend(load(p))
    
    return images

def check_output(output: str):
    try:
        open(output, 'w')
    except IOError:
        print("%s could not be written! This might be due to permissions or an invalid path" % output)
        return False
    
    if os.path.splitext(output)[1] == '':
        print("%d doesn't have an extension!" % output)
        return False
    
    return True

def parse_arguments():
    parser = argparse.ArgumentParser(description="A simple program for packing multiple images together into an atlas")
    parser.add_argument('-2', '--pow2', action='store_true', required=False, help="Output image's sides' length will be a power of 2")
    parser.add_argument('-s', '--square', action='store_true', required=False, help="Output image will be a square")
    parser.add_argument('-verbose', action='store_true', required=False, help="Verbose logging")
    parser.add_argument('-o', '--output', required=True, help="Output image destination")
    parser.add_argument('-i', '--input', required=True, nargs='+', help="Input image(s) path(s)")

    args = parser.parse_args()
    return args.pow2, args.square, args.verbose, args.output, args.input

def main(pow2, sq, verbose, output, inputs):
    if not check_output(output):
        exit()

    imgs = []
    for i in inputs:
        imgs = load(i)

    if len(imgs) == 0:
        print("No images were loaded! Wrong path? Or maybe they are unsupported format")
        return
    
    tree, w, h = generate_tree(imgs, pow2, sq)

    result = tree_into_image(tree, w, h)

    try:
        print("Saving to %s" % output)
        result.save(output)
    except ValueError:
        print("Couldn't determine output format from file name")
    except IOError:
        print("Couldn't write to %s" % output)


if __name__ == "__main__":
	global verbose
    pow2, sq, verbose, output, inputs = parse_arguments()
    main(pow2, sq, verbose, output, inputs)