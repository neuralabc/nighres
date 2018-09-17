import numpy as np
import nibabel as nb
import os
import sys
import nighresjava
from ..io import load_volume, save_volume
from ..utils import _output_dir_4saving, _fname_4saving, \
                    _check_topology_lut_dir


def background_estimation(image, distribution='exponential', ratio=1e-3,
                          skip_zero=True,
                          save_data=False, overwrite=False, output_dir=None,
                          file_name=None):
    """ Background Estimation

    Estimates image background by robustlyfitting various distribution models

    Parameters
    ----------
    image: niimg
        Input image
    distribution: {'exponential','half-normal'}
        Distribution model to use for the background noise
    ratio: float, optional 
        Robustness ratio for estimating image intensities
   skip_zero: bool, optional
        Whether to consider or skip zero values
    save_data: bool
        Save output data to file (default is False)
    overwrite: bool
        Overwrite existing results (default is False)
    output_dir: str, optional
        Path to desired output directory, will be created if it doesn't exist
    file_name: str, optional
        Desired base name for output files with file extension
        (suffixes will be added)

    Returns
    ----------
    dict
        Dictionary collecting outputs under the following keys
        (suffix of output files in brackets)

        * masked (niimg): The background-masked input image
        * proba (niimg): The probability map of the foreground

    Notes
    ----------
    Original Java module by Pierre-Louis Bazin.

    """

    print('\nBackgeround Estimation')

    # make sure that saving related parameters are correct
    if save_data:
        output_dir = _output_dir_4saving(output_dir, image)

        masked_file = os.path.join(output_dir, 
                        _fname_4saving(file_name=file_name,
                                   rootfile=image,
                                   suffix='bge-masked'))

        proba_file = os.path.join(output_dir, 
                        _fname_4saving(file_name=file_name,
                                   rootfile=image,
                                   suffix='bge-proba'))

        if overwrite is False \
            and os.path.isfile(masked_file) and os.path.isfile(proba_file) :
                print("skip computation (use existing results)")
                output = {'masked': load_volume(masked_file), 
                          'proba': load_volume(proba_file)}
                return output

    # start virtual machine, if not already running
    try:
        nighresjava.initVM(initialheap='12000m', maxheap='12000m')
    except ValueError:
        pass
    # create instance
    bge = nighresjava.IntensityBackgroundEstimator()

    # set parameters
    
    # load image and use it to set dimensions and resolution
    img = load_volume(image)
    data = img.get_data()
    affine = img.get_affine()
    header = img.get_header()
    resolution = [x.item() for x in header.get_zooms()]
    dimensions = data.shape

    bge.setDimensions(dimensions[0], dimensions[1], dimensions[2])
    bge.setResolutions(resolution[0], resolution[1], resolution[2])

    bge.setInputImage(nighresjava.JArray('float')(
                                    (data.flatten('F')).astype(float)))
    
    # set algorithm parameters
    bge.setBackgroundDistribution(distribution)
    bge.setRobustMinMaxThresholding(ratio)
    bge.setSkipZeroValues(skip_zero)
    
    # execute the algorithm
    try:
        bge.execute()

    except:
        # if the Java module fails, reraise the error it throws
        print("\n The underlying Java code did not execute cleanly: ")
        print(sys.exc_info()[0])
        raise
        return

    # reshape output to what nibabel likes
    masked_data = np.reshape(np.array(bge.getMaskedImage(),
                                    dtype=np.float32), dimensions, 'F')

    # adapt header max for each image so that correct max is displayed
    # and create nifiti objects
    header['cal_min'] = np.nanmin(masked_data)
    header['cal_max'] = np.nanmax(masked_data)
    masked = nb.Nifti1Image(masked_data, affine, header)

    proba_data = np.reshape(np.array(bge.getProbaImage(),
                                    dtype=np.float32), dimensions, 'F')

    # adapt header max for each image so that correct max is displayed
    # and create nifiti objects
    header['cal_min'] = np.nanmin(proba_data)
    header['cal_max'] = np.nanmax(proba_data)
    proba = nb.Nifti1Image(proba_data, affine, header)

    if save_data:
        save_volume(masked_file, masked)
        save_volume(proba_file, proba)

    return {'masked': masked, 'proba': proba}
