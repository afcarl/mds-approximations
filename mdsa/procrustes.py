from warnings import warn

import numpy as np
from scipy.spatial import procrustes as scipy_procrustes
from skbio import OrdinationResults

"""
Refactored, updated for skbio 0.5.1 API & optimized by Hannes Holste.

Based on contributions to QIIME1 by Greg Caporaso, Justin Kuczynski,
Jose Carlos Clemente Litran, Jose Antonio Navas Molina.
"""


def procrustes_monte_carlo(reference_matrix,
                           input_matrix,
                           trials=1000):
    # Calculate m^2 for original matrices
    m_squared_actual = procrustes(reference_matrix, input_matrix)

    # Calculate m^2 for each random trial
    m_squared_trials = []
    count_better = 0
    for i in range(trials):
        # Perform the procrustes analysis random trial
        # with rows in the given reference matrix shuffled for each
        # random trial (Justin Kuczynski this type of shuffling is appropriate
        # for procrustes monte carlo)
        m_squared_trial = procrustes(reference_matrix, input_matrix,
                                     randomize_fn=np.random.shuffle)
        m_squared_trials.append(m_squared_trial)

        if m_squared_trial <= m_squared_actual:
            count_better += 1

    return m_squared_actual, m_squared_trials, count_better


def procrustes(reference_matrix, input_matrix, randomize_fn=None):
    if (not isinstance(reference_matrix, OrdinationResults) or
            not isinstance(input_matrix, OrdinationResults)):
        raise ValueError('Expecting input and reference matrix to be'
                         ' of type skbio OrdinationResults')

    in_sample_ids = input_matrix.samples.index.values.tolist()
    ref_sample_ids = reference_matrix.samples.index.values.tolist()
    in_matrix = input_matrix.samples.values
    ref_matrix = reference_matrix.samples.values

    # Sorting step
    # Because scipy.spatial.procrustes produces differing m^2 results for
    # differing order of rows in each matrix passed, we need to re-arrange
    # the rows (i.e. samples) in input_matrix and reference_matrix, to ensure
    # consistent ordering (by sample id) and thus repeatability of results

    # The master order is simply an ascending sort of the sample ids
    # contained in both the input and reference matrix
    order = list(set(in_sample_ids) & set(ref_sample_ids))

    if len(order) == 0:
        raise ValueError(
            'No overlapping sample IDs in the two OrdinationResults '
            'matrices.')
    elif len(order) != len(in_sample_ids) or len(order) != len(ref_sample_ids):
        warn('Procrustes: some sample ids of input_matrix do not overlap with '
             'sample ids of reference_matrix. Non-overlapping corresponding '
             'samples in matrices will be dropped for procrustes procedure.',
             RuntimeWarning
             )
    in_matrix = _reorder_rows(in_matrix, in_sample_ids, order)
    ref_matrix = _reorder_rows(ref_matrix, ref_sample_ids, order)

    # If randomization function given, use it to shuffle the reference matrix
    # (used for monte carlo random trial)
    if randomize_fn:
        return_matrix = randomize_fn(ref_matrix)

        # if randomize_fn did not shuffle in-place, then update ref_matrix
        # with the shuffled return_matrix manually
        if return_matrix is not None:
            ref_matrix = return_matrix

    # Apply padding to matrices to ensure equal dimensionality
    in_matrix, ref_matrix = _pad_matrices(in_matrix, ref_matrix)

    # Run the Procrustes analysis
    in_matrix_transformed, ref_matrix_transformed, m_squared = \
        scipy_procrustes(ref_matrix, in_matrix)
    return m_squared


def calc_p_value(trials, count_better):
    """
    Calculate p-value and truncate to appropriate number of significant digits
    (significant digits scaled logarithmically to number of trials).

    """
    pval = float(count_better) / float(trials)
    decimal_places = int(np.log10(trials + 1))
    return float(('%1.' + '%df' % decimal_places) % pval)


def _reorder_rows(matrix, sample_ids, order):
    """ Arrange the rows in matrix to correspond to order

        Note: order is the master list here -- if a sample id is
        not included in order, that coord will not be included in
        the results. All sample ids in order however must be in
        sample_ids

    """
    result = []
    for sample_id in order:
        try:
            result.append(matrix[sample_ids.index(sample_id)])

        except Exception:
            raise ValueError(
                'Procrustes row reordering encountered sample ID in matrix '
                'not present in given, desired ordering: %s' % sample_id)

    return np.array(result)


def _pad_matrices(matrix_a, matrix_b):
    """
    Pad matrices to ensure that matrix_a has same number of columns as matrix_b

    """
    matrix_a = np.array(matrix_a)
    matrix_b = np.array(matrix_b)

    # Determine how many dimensions are in each vector
    a_len = matrix_a.shape[1]
    b_len = matrix_b.shape[1]
    len_diff = a_len - b_len

    pad = abs(len_diff)

    # If the first vector is shorter, pad it with zeros
    if len_diff < 0:
        matrix_a = _pad_matrix(matrix_a, pad)
    # If the second vector is shorter, pad it with zeros
    elif len_diff > 0:
        matrix_b = _pad_matrix(matrix_b, pad)

    return matrix_a, matrix_b


def _pad_matrix(matrix, dimensions_to_add):
    """
    Pad the end of each row in matrix with dimensions_to_add number of zeros.

    """
    if dimensions_to_add < 0:
        raise ValueError('Dimensions to add must be >= 0.')
    elif dimensions_to_add == 0:
        return np.array(matrix)
    else:
        return np.pad(matrix, [(0, 0), (0, dimensions_to_add)], 'constant')
