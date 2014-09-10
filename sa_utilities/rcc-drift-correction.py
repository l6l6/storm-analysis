#!/usr/bin/python
#
# A Python implementation of the drift algorithm described in this reference:
#
# "Localization events-based sample drift correction for localization microscopy with redundant cross-correlation algorithm", 
# Wang et al. Optics Express, 30 June 2014, Vol. 22, No. 13, DOI:10.1364/OE.22.015982.
#
# This uses the above algorithm for XY correction, then falls back to old
# approach for the Z correction.
#
# Hazen 09/14
#

import numpy
import os
import scipy.signal
import sys

import sa_library.arraytoimage as arraytoimage
import sa_library.i3togrid as i3togrid
import sa_library.imagecorrelation as imagecorrelation


# Setup
if (len(sys.argv) < 5):
    print "usage: <bin> <drift.txt> <step> <scale> <optional - z_correct>"
    exit()

step = int(sys.argv[3])
scale = int(sys.argv[4])
i3_data = i3togrid.I3GDataLL(sys.argv[1], scale = scale)
film_l = i3_data.getFilmLength()

if film_l < step:
    sys.exit()

correct_z = True
if (len(sys.argv) > 5):
    correct_z = False

film_l = 10200

endpost = film_l - step/2
start1 = 0
end1 = start1 + step
start2 = start1
end2 = start2 + step
while (start1 < endpost):

    if (start2 > endpost):
        print ""
        start1 += step
        end1 = start1 + step
        start2 = start1
        end2 = start2 + step
        if (end1 > endpost):
            end1 = film_l
        if (end2 > endpost):
            end2 = film_l

    if (start1 > endpost):
        continue

    print start1, "-" , end1 , "  ", start2, "-", end2

    start2 += step
    end2 = start2 + step
    if (end2 > endpost):
        end2 = film_l

print "--"
print film_l

exit()

# Compute all offset pairs.
i3_data.loadDataInFrames(fmin = start, fmax = start+step)
xymaster = i3_data.i3To2DGridAllChannelsMerged(uncorrected = True)

if correct_z:
    z_bins = 20
    xyzmaster = i3_data.i3To3DGridAllChannelsMerged(z_bins,
                                                    uncorrected = True)

index = 1
last = 0
step_step = 0
if(start>0):
    j = 0
else:
    j = step
t = [step/2]
x = [0]
y = [0]
z = [0]
old_dx = 0.0
old_dy = 0.0
old_dz = 0.0
while(j < film_l):

    # Load correct frame range.
    last = j
    if ((j + 2*step) >= film_l):
        i3_data.loadDataInFrames(fmin = j)
        step_step = 2*step
    else:
        i3_data.loadDataInFrames(fmin = j, fmax = j + step)
        step_step = step

    xycurr = i3_data.i3To2DGridAllChannelsMerged(uncorrected = True)

    # Correlate to master image.
    [corr, dx, dy, xy_success] = imagecorrelation.xyOffset(xymaster,
                                                           xycurr,
                                                           i3_data.getScale(),
                                                           center = [x[index-1] * scale,
                                                                     y[index-1] * scale])

    # Update values
    if xy_success:
        old_dx = dx
        old_dy = dy
    else:
        dx = old_dx
        dy = old_dy

    dx = dx/float(scale)
    dy = dy/float(scale)

    t.append(step/2 + index * step)
    x.append(dx)
    y.append(dy)

    i3_data.applyXYDriftCorrection(dx,dy)
    if xy_success:
        # Add current to master
        xymaster += i3_data.i3To2DGridAllChannelsMerged()

    # Z correlation
    dz = old_dz
    if correct_z and xy_success:

        xyzcurr = i3_data.i3To3DGridAllChannelsMerged(z_bins,
                                                      uncorrected = True)

        # Do z correlation
        [corr, fit, dz, z_success] = imagecorrelation.zOffset(xyzmaster, xyzcurr)

        # Update Values
        if z_success:
            old_dz = dz
        else:
            dz = old_dz
            
        dz = dz * 1000.0/float(z_bins)

        if z_success:
            i3_data.applyZDriftCorrection(-dz)
            xyzmaster += i3_data.i3To3DGridAllChannelsMerged(z_bins)
    
    z.append(dz)

    print index, dx, dy, dz

    index += 1
    j += step_step

i3_data.close()

# Solve for the drift.

# Create numpy versions of the drift arrays.
nt = numpy.array(t)
nx = numpy.array(x)
ny = numpy.array(y)
nz = numpy.array(z)

# Use a cubic spline to interpolate drift correction values
# for each frame of the movie.
smootht = numpy.arange(0, film_l)
cjx = scipy.signal.cspline1d(nx)
cjy = scipy.signal.cspline1d(ny)
cjz = scipy.signal.cspline1d(nz)
smoothx = scipy.signal.cspline1d_eval(cjx, smootht, dx=step, x0=step/2)
smoothy = scipy.signal.cspline1d_eval(cjy, smootht, dx=step, x0=step/2)
smoothz = scipy.signal.cspline1d_eval(cjz, smootht, dx=step, x0=step/2)

# Pad out the end points.
smoothx[0:step/2] = 0.0
smoothy[0:step/2] = 0.0
smoothz[0:step/2] = 0.0

smoothx[last:film_l] = smoothx[last]
smoothy[last:film_l] = smoothy[last]
smoothz[last:film_l] = smoothz[last]

# Save the results in Insight drift correction format.
numpy.savetxt(sys.argv[2],
              numpy.column_stack((smootht + 1, -smoothx, -smoothy, smoothz)),
              fmt = "%d\t%.3f\t%.3f\t%.3f")


#
# The MIT License
#
# Copyright (c) 2012 Zhuang Lab, Harvard University
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
