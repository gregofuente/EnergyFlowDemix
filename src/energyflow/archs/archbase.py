r"""# Architectures

Energy Flow Networks (EFNs) and Particle Flow Networks (PFNs) are model
architectures designed for learning from collider events as unordered,
variable-length sets of particles. Both EFNs and PFNs are parameterized by a
learnable per-particle function $\Phi$ and latent space function $F$.

An EFN takes the following form:

$$\text{EFN}=F\left(\sum_{i=1}^M z_i \Phi(\hat p_i)\right)$$

where $z_i$ is a measure of the energy of particle $i$, such as $z_i=p_{T,i}$,
and $\hat p_i$ is a measure of the angular information of particle $i$, such as
$\hat p_i = (y_i,\phi_i)$. Any infrared- and collinear-safe observable can be
parameterized in this form.

A PFN takes the following form:

$$\text{PFN}=F\left(\sum_{i=1}^M \Phi(p_i)\right)$$

where $p_i$ is the information of particle $i$, such as its four-momentum,
charge, or flavor. Any observable can be parameterized in this form. See the
[Deep Sets](https://arxiv.org/abs/1703.06114) framework for additional
discussion.

Since these architectures are not used by the core EnergyFlow code, and require
the external [TensorFlow](https://www.tensorflow.org) and [scikit-learn](http:
//scikit-learn.org/) libraries, they are not imported by default but must be
explicitly imported, e.g. `from energyflow.archs import *`. EnergyFlow also
contains several additional model architectures for ease of using common models
that frequently appear in the intersection of particle physics and machine
learning.
"""

#           _____   _____ _    _ ____           _____ ______
#     /\   |  __ \ / ____| |  | |  _ \   /\    / ____|  ____|
#    /  \  | |__) | |    | |__| | |_) | /  \  | (___ | |__
#   / /\ \ |  _  /| |    |  __  |  _ < / /\ \  \___ \|  __|
#  / ____ \| | \ \| |____| |  | | |_) / ____ \ ____) | |____
# /_/    \_\_|  \_\\_____|_|  |_|____/_/    \_\_____/|______|

# EnergyFlow - Python package for high-energy particle physics.
# Copyright (C) 2017-2022 Patrick T. Komiske III and Eric Metodiev

from __future__ import absolute_import, division, print_function

from abc import ABCMeta, abstractmethod, abstractproperty
import gc
import os
import warnings

from tf_keras.callbacks import ModelCheckpoint, EarlyStopping
from tf_keras.layers import Activation, Layer, LeakyReLU, PReLU, ThresholdedReLU
from tf_keras.models import Model

from tf_keras import backend as K
from tf_keras.losses import Loss
from tf_keras.initializers import Constant

from energyflow.utils import iter_or_rep

__all__ = ['ArchBase', 'NNBase']

###############################################################################
# ArchBase
###############################################################################

class ArchBase(object, metaclass=ABCMeta):

    """Base class for all architectures contained in EnergyFlow. The mechanism of
    specifying hyperparameters for all architectures is described here. Methods
    common to all architectures are documented here. Note that this class cannot
    be instantiated directly as it is an abstract base class.
    """

    # ArchBase(*args, **kwargs)
    def __init__(self, *args, **kwargs):
        """Accepts arbitrary arguments. Positional arguments (if present) are
        dictionaries of hyperparameters, keyword arguments (if present) are
        hyperparameters directly. Keyword hyperparameters take precedence over
        positional hyperparameter dictionaries.

        **Arguments**

        - ***args** : arbitrary positional arguments
            - Each argument is a dictionary containing hyperparameter (name, value)
            pairs.
        - ***kwargs** : arbitrary keyword arguments
            - Hyperparameters as keyword arguments. Takes precedence over the
            positional arguments.
        """

        # store all options
        self.hps = {}
        for d in args:
            self.hps.update(d)
        self.hps.update(kwargs)

        # process hyperparameters
        self._process_hps()

        # construct model
        self._construct_model()

    def _proc_arg(self, name, **kwargs):
        if 'old' in kwargs and kwargs['old'] in self.hps:
            old = kwargs['old']
            m = ('\'{}\' is deprecated and will be removed in the future, '
                 'use \'{}\' instead.').format(old, name)
            warnings.warn(FutureWarning(m))
            kwargs['default'] = self.hps.pop(old)

        return (self.hps.pop(name, kwargs['default']) if 'default' in kwargs
                                                      else self.hps.pop(name))

    def _verify_empty_hps(self):

        # hps should be all empty now
        for k in self.hps:
            raise ValueError('unrecognized keyword argument {}'.format(k))

        del self.hps

    @abstractmethod
    def _process_hps(self):
        pass

    @abstractmethod
    def _construct_model(self):
        pass

    # fit(*args, **kwargs)
    @abstractmethod
    def fit(self):
        """Train the model by fitting the provided training dataset and labels.
        Transparently calls the `.fit()` method of the underlying model.

        **Arguments**

        - ***args** : _numpy.ndarray_ or _tensorflow.data.Dataset_
            - Either the `X_train` and `Y_train` NumPy arrays or a TensorFlow
            dataset.
        - **kwargs** : _dict_
            - Keyword arguments passed on to the `.fit()` method of the
            underlying model. Most relevant for neural network models, where the
            [TensorFlow/Keras model docs](https://www.tensorflow.org/api_docs/
            python/tf/keras/Model#fit) contain detailed information on the
            possible arguments.

        **Returns**

        - The return value of the the underlying model's `.fit()` method.
        """

        pass

    # predict(X_test, **kwargs)
    @abstractmethod
    def predict(self):
        """Evaluate the model on a dataset. Note that for the `LinearClassifier`
        this corresponds to the `predict_proba` method of the underlying
        scikit-learn model.

        **Arguments**

        - **X_test** : _numpy.ndarray_
            - The dataset to evaluate the model on.
        - **kwargs** : _dict_
            - Keyword arguments passed on to the underlying model when
            predicting on a dataset.

        **Returns**

        - _numpy.ndarray_
            - The value of the model on the input dataset.
        """

        pass

    @abstractproperty
    def model(self):
        """The underlying model held by this architecture. Note that accessing
        an attribute that the architecture does not have will resulting in
        attempting to retrieve the attribute from this model. This allows for
        interrogation of the EnergyFlow architecture in the same manner as the
        underlying model.

        **Examples**

        - For neural network models:
            - `model.layers` will return a list of the layers, where
            `model` is any EnergFlow neural network.
        - For linear models:
            - `model.coef_` will return the coefficients, where `model`
            is any EnergyFlow `LinearClassifier` instance.
        """

        pass

    # pass on unknown attribute lookups to the underlying model
    def __getattr__(self, attr):

        if hasattr(self.model, attr):
            return getattr(self.model, attr)

        else:
            name = self.__class__.__name__
            raise AttributeError("'{}' object has no attribute '{}', ".format(name, attr)
                                 + "check of underlying model failed")
        
###############################################################################
# Thin wrapper implemented using the tf_keras backend
###############################################################################

class DeMixer(Model):
    def __init__(self, output_dim, number_cat, alpha, architecture, **kwargs):
        super().__init__(**kwargs)

        # Save attributes 
        self.output_dim = output_dim
        self.number_cat = number_cat 
        self.alpha      = alpha 

        # Save inner model 
        self.architecture = architecture

        self.raw_fractions = self.add_weight(
            shape=(output_dim, number_cat),
            #initializer="random_normal",
            initializer=Constant(K.eye(output_dim)[:, :number_cat]),
            trainable=True
        )

    def getFractions(self):
        return K.softmax(self.raw_fractions, axis=1)
    
    def getVertices(self):
        return to_vertices(self.raw_fractions)

    def call(self, inputs):
        # Obtain outputs on inner architecture
        # We assume that the output activation function is set to SOFTMAX
        barycentric = self.architecture(inputs)

        self.add_loss(lambda: self.alpha * perimeterLoss(self.raw_fractions))

        # This is equivalent to tf.matmul when barycentric and vertices are 2D arrays,
        # which they are in this case
        vertices        = to_vertices(self.raw_fractions)
        outputs         = K.dot(barycentric, vertices)

        return outputs 
    
def to_vertices(raw_fractions):
    # Calculate the vertex matrix 
    fractions       = K.softmax(raw_fractions, axis=1)
    raw_vertices    = K.transpose(fractions)
    denominator     = K.expand_dims(K.sum(raw_vertices, axis=1), axis=-1)
    vertices        = raw_vertices/denominator 

    return vertices

def perimeterLoss(raw_fractions):
    vertices        = to_vertices(raw_fractions)

    A               = K.expand_dims(vertices, axis=0)
    B               = K.expand_dims(vertices, axis=1)
    pws_squares     = K.sum(K.square(A - B), axis=-1)
    pws_distances   = K.sqrt(pws_squares + 1e-9)
    edge_lengths    = 0.5*K.sum(pws_distances)

    return edge_lengths


###############################################################################
# NNBase
###############################################################################

class NNBase(ArchBase):

    def __init__(self, *args, **kwargs):
        '''
        A NNBase object has the additional property that it can be demixed.
        '''
        # After calling ArchBase's init:
        # 1. The hyperparameters are processed according to _process_hps
        # 2. A _model object is constructed and compiled according to _construct_model
        super().__init__(*args, **kwargs)

        # Construct the demixer
        if (self.mode == 'demix'):
            self._construct_demixer()
        else:
            pass

    def _process_hps(self):
        """**Default NN Hyperparameters**

        Common hyperparameters that apply to all architectures except for
        [`LinearClassifier`](#linearclassifier).

        **Compilation Options**

        - **loss**=`'categorical_crossentropy'` : _str_
            - The loss function to use for the model. See the [Keras loss
            function docs](https://keras.io/losses/) for available loss
            functions.
        - **optimizer**=`'adam'` : Keras optimizer or _str_
            - A [Keras optimizer](https://keras.io/optimizers/) instance or a
            string referring to one (in which case the default arguments are
            used).
        - **metrics**=`['accuracy']` : _list_ of _str_
            - The [Keras metrics](https://keras.io/metrics/) to apply to the
            model.
        - **compile_opts**=`{}` : _dict_
            - Dictionary of keyword arguments to be passed on to the
            [`compile`](https://keras.io/models/model/#compile) method of the
            model. `loss`, `optimizer`, and `metrics` (see above) are included
            in this dictionary. All other values are the Keras defaults.

        **Output Options**

        - **output_dim**=`2` : _int_
            - The output dimension of the model.
        - **output_act**=`'softmax'` : _str_ or Keras activation
            - Activation function to apply to the output.

        **Callback Options**

        - **filepath**=`None` : _str_
            - The file path for where to save the model. If `None` then the
            model will not be saved.
        - **save_while_training**=`True` : _bool_
            - Whether the model is saved during training (using the
            [`ModelCheckpoint`](https://keras.io/callbacks/#modelcheckpoint)
            callback) or only once training terminates. Only relevant if
            `filepath` is set.
        - **save_weights_only**=`False` : _bool_
            - Whether only the weights of the model or the full model are
            saved. Only relevant if `filepath` is set.
        - **modelcheck_opts**=`{'save_best_only':True, 'verbose':1}` : _dict_
            - Dictionary of keyword arguments to be passed on to the
            [`ModelCheckpoint`](https://keras.io/callbacks/#modelcheckpoint)
            callback, if it is present. `save_weights_only` (see above) is
            included in this dictionary. All other arguments are the Keras
            defaults.
        - **patience**=`None` : _int_
            - The number of epochs with no improvement after which the training
            is stopped (using the [`EarlyStopping`](https://keras.io/
            callbacks/#earlystopping) callback). If `None` then no early stopping
            is used.
        - **earlystop_opts**=`{'restore_best_weights':True, 'verbose':1}` : _dict_
            - Dictionary of keyword arguments to be passed on to the
            [`EarlyStopping`](https://keras.io/callbacks/#earlystopping)
            callback, if it is present. `patience` (see above) is included in
            this dictionary. All other arguments are the Keras defaults.

        **Flags**

        - **name_layers**=`True` : _bool_
            - Whether to give the layers of the model explicit names or let
            them be named automatically. One reason to set this to `False`
            would be in order to use parts of this model in another model
            (all Keras layers in a model are required to have unique names).
        - **compile**=`True` : _bool_
            - Whether the model should be compiled or not.
        - **summary**=`True` : _bool_
            - Whether a summary should be printed or not.
        """

        # compilation
        self.compile_opts = {'loss': self._proc_arg('loss', default='categorical_crossentropy'),
                             'optimizer': self._proc_arg('optimizer', default='adam'),
                             'metrics': self._proc_arg('metrics', default=['acc'])}
        self.compile_opts.update(self._proc_arg('compile_opts', default={}))

        # add these attributes for historical reasons
        self.loss = self.compile_opts['loss']
        self.optimizer = self.compile_opts['optimizer']
        self.metrics = self.compile_opts['metrics']

        # output
        self.output_dim = self._proc_arg('output_dim', default=2)
        self.output_act = self._proc_arg('output_act', default='softmax')

        # callbacks
        self.filepath = self._proc_arg('filepath', default=None)
        if self.filepath is not None:
            self.filepath = os.path.expanduser(self.filepath)
        self.save_while_training = self._proc_arg('save_while_training', default=True)
        self.modelcheck_opts = {'save_best_only': True, 'verbose': 1,
                'save_weights_only': self._proc_arg('save_weights_only', default=False)}
        self.modelcheck_opts.update(self._proc_arg('modelcheck_opts', default={}))
        self.save_weights_only = self.modelcheck_opts['save_weights_only']

        self.earlystop_opts = {'restore_best_weights': True, 'verbose': 1,
                               'patience': self._proc_arg('patience', default=None)}
        self.earlystop_opts.update(self._proc_arg('earlystop_opts', default={}))
        self.patience = self.earlystop_opts['patience']

        # flags
        self.name_layers = self._proc_arg('name_layers', default=True)
        self.compile = self._proc_arg('compile', default=True)
        self.summary = self._proc_arg('summary', default=True)

        # Number of categories (For the demixer)
        self.number_cat = self._proc_arg('number_cat', default=self.output_dim)
        allowed_modes   = {'demix', 'plain'}
        self.mode       = self._proc_arg('mode', default='demix').lower()
        self.alpha      = self._proc_arg('alpha', default=0.0001)

        if self.mode not in allowed_modes:
            raise ValueError(
                f"Unrecognised mode '{self.mode}'. "
                f"Valid options are {sorted(allowed_modes)}."
            )
        
        # Update output_dim to ensure correct output dimension of the inner model
        if (self.mode == 'demix'):
            self.demixer_output_dim     = self.output_dim
            self.output_dim             = self.number_cat
        else:
            pass

    def _add_act(self, act):

        # handle case of act as a layer
        if isinstance(act, Layer):
            self.model.add(act)

        # handle case of act being a string and in ACT_DICT
        elif isinstance(act, str) and act in ACT_DICT:
            self.model.add(ACT_DICT[act]())

        # default case of regular activation
        else:
            self.model.add(Activation(act))

    def _proc_name(self, name):
        return name if self.name_layers else None

    def _compile_model(self):

        # compile model if specified
        if self.compile:
            self.model.compile(**self.compile_opts)

            # print summary
            if self.summary:
                self.model.summary()

    def _compile_demixer(self):
        '''
        Instructions to compile the demixer. In the future, might want to add different arguments for the demixer.
        '''
        # compile model if specified
        if self.compile:
            self.demixer.compile(**self.compile_opts)

            # # print summary
            # if self.summary:
            #     self.demixer.summary()

    def _construct_demixer(self):

        self._demixer = DeMixer(output_dim=self.demixer_output_dim, number_cat=self.number_cat, alpha=self.alpha, architecture=self.model)
        
        # self._demixer.build(self._model.input_shape)

        self._compile_demixer()

    def fit(self, *args, **kwargs):

        if (self.mode == 'demix'):
            fitTarget = self.demixer
        else:
            fitTarget = self.model 

        # list of callback functions
        callbacks = []

        # do model checkpointing, used mainly to save model during training instead of at end
        if self.filepath and self.save_while_training:
            callbacks.append(ModelCheckpoint(self.filepath, **self.modelcheck_opts))

        # do early stopping, which now also handle loading best weights at the end
        if self.patience is not None:
            callbacks.append(EarlyStopping(**self.earlystop_opts))

        # update any callbacks that were passed with the two we build in explicitly
        kwargs.setdefault('callbacks', []).extend(callbacks)

        # do the fitting
        hist = fitTarget.fit(*args, **kwargs)

        # handle saving at the end, if we weren't already saving throughout
        if self.filepath and not self.save_while_training:
            if self.save_weights_only:
                fitTarget.save_weights(self.filepath)
            else:
                fitTarget.save(self.filepath)

        # take out the trash
        gc.collect()

        return hist

    def predict(self, *args, **kwargs):

        if (self.mode == 'demix'):
            predictTarget = self.demixer
        else:
            predictTarget = self.model 

        return predictTarget.predict(*args, **kwargs)

    @property
    def model(self):
        if hasattr(self, '_model'):
            return self._model
        else:
            name = self.__class__.__name__
            raise AttributeError("'{}' object has no underlying model".format(name))
        
    @property
    def demixer(self):
        if hasattr(self, '_demixer'):
            return self._demixer
        else:
            name = self.__class__.__name__
            raise AttributeError("'{}' object has no underlying demixer".format(name))


###############################################################################
# Activation Functions
###############################################################################

ACT_DICT = {'LeakyReLU': LeakyReLU, 'PReLU': PReLU, 'ThresholdedReLU': ThresholdedReLU}

def _get_act_layer(act):

    # handle case of act as a layer
    if isinstance(act, Layer):
        return act

    # handle case of act being a string and in ACT_DICT
    if isinstance(act, str) and act in ACT_DICT:
        return ACT_DICT[act]()

    # default case of passing act into layer
    return Activation(act)
