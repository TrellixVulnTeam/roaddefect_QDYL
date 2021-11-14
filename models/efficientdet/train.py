#-------------------------------------#
#       Dataset Training
#-------------------------------------#
import numpy as np
import torch
import torch.backends.cudnn as cudnn
import torch.optim as optim
from torch.utils.data import DataLoader

from nets.efficientdet import EfficientDetBackbone
from nets.efficientdet_training import FocalLoss
from utils.callbacks import LossHistory
from utils.dataloader import EfficientdetDataset, efficientdet_dataset_collate
from utils.utils import get_classes, image_sizes
from utils.utils_fit import fit_one_epoch

if __name__ == "__main__":
    #-------------------------------#
    #   Cuda or not, for CPU set to False
    #-------------------------------#
    Cuda            = True
    #--------------------------------------------------------#
    #   Object category
    #--------------------------------------------------------#
    classes_path    = 'model_data/rdd_classes.txt'
    #---------------------------------------------------------------------#
    #   EfficientDet model version, 0-7
    #---------------------------------------------------------------------#
    phi             = 0
    pretrained      = False
    #----------------------------------------------------------------------------------------------------------------------------#
    #   pretrained model path
    #----------------------------------------------------------------------------------------------------------------------------#
    model_path      = 'model_data/efficientdet-d0.pth'
    #------------------------------------------------------#
    #   image size
    #------------------------------------------------------#
    input_shape     = [image_sizes[phi], image_sizes[phi]]
    
    #----------------------------------------------------#
    #   Training is devided into two parts: Freeze and unFreeze
    #----------------------------------------------------#
    #----------------------------------------------------#
    #   Freeze stage, backbone is frozen, feature extraction won't change
    #----------------------------------------------------#
    Init_Epoch          = 0
    Freeze_Epoch        = 30
    Freeze_batch_size   = 8
    Freeze_lr           = 1e-3
    #----------------------------------------------------#
    #   unFreeze stage, backbone parameter is also taken into adjustment
    #----------------------------------------------------#
    UnFreeze_Epoch      = 50
    Unfreeze_batch_size = 4
    Unfreeze_lr         = 1e-4
    #------------------------------------------------------#
    #   whether to use freeze training
    #------------------------------------------------------#
    Freeze_Train        = True
    num_workers         = 4
    train_annotation_path   = '2007_train.txt'
    val_annotation_path     = '2007_val.txt'
    #----------------------------------------------------#
    #   get classes and anchor
    #----------------------------------------------------#
    class_names, num_classes = get_classes(classes_path)

    #------------------------------------------------------#
    #   Create EfficientDet model
    #------------------------------------------------------#
    model = EfficientDetBackbone(num_classes, phi, pretrained)

    if model_path != '':
        print('Load weights {}.'.format(model_path))
        device          = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model_dict      = model.state_dict()
        pretrained_dict = torch.load(model_path, map_location = device)
        pretrained_dict = {k: v for k, v in pretrained_dict.items() if np.shape(model_dict[k]) == np.shape(v)}
        model_dict.update(pretrained_dict)
        model.load_state_dict(model_dict)

    model_train = model.train()
    if Cuda:
        model_train = torch.nn.DataParallel(model)
        cudnn.benchmark = True
        model_train = model_train.cuda()

    focal_loss      = FocalLoss()
    loss_history    = LossHistory("logs/")

    with open(train_annotation_path) as f:
        train_lines = f.readlines()
    with open(val_annotation_path) as f:
        val_lines   = f.readlines()
    num_train   = len(train_lines)
    num_val     = len(val_lines)

    if True:
        batch_size  = Freeze_batch_size
        lr          = Freeze_lr
        start_epoch = Init_Epoch
        end_epoch   = Freeze_Epoch
        
        optimizer       = optim.Adam(model_train.parameters(), lr, weight_decay = 5e-4)
        lr_scheduler    = optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.94)

        train_dataset   = EfficientdetDataset(train_lines, input_shape, num_classes, train = True)
        val_dataset     = EfficientdetDataset(val_lines, input_shape, num_classes, train = False)
        gen             = DataLoader(train_dataset, shuffle = True, batch_size = batch_size, num_workers = num_workers, pin_memory=True,
                                    drop_last=True, collate_fn=efficientdet_dataset_collate)
        gen_val         = DataLoader(val_dataset  , shuffle = True, batch_size = batch_size, num_workers = num_workers, pin_memory=True, 
                                    drop_last=True, collate_fn=efficientdet_dataset_collate)
                        
        epoch_step      = num_train // batch_size
        epoch_step_val  = num_val // batch_size
        
        if epoch_step == 0 or epoch_step_val == 0:
            raise ValueError("Dataset too small. Unable to train.")

        if Freeze_Train:
            for param in model.backbone_net.parameters():
                param.requires_grad = False
                
        for epoch in range(start_epoch, end_epoch):
            fit_one_epoch(model_train, model, focal_loss, loss_history, optimizer, epoch, 
                    epoch_step, epoch_step_val, gen, gen_val, end_epoch, Cuda)
            lr_scheduler.step()
            
    if True:
        batch_size  = Unfreeze_batch_size
        lr          = Unfreeze_lr
        start_epoch = Freeze_Epoch
        end_epoch   = UnFreeze_Epoch
        
        optimizer       = optim.Adam(model_train.parameters(), lr, weight_decay = 5e-4)
        lr_scheduler    = optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.94)

        train_dataset   = EfficientdetDataset(train_lines, input_shape, num_classes, train = True)
        val_dataset     = EfficientdetDataset(val_lines, input_shape, num_classes, train = False)
        gen             = DataLoader(train_dataset, shuffle = True, batch_size = batch_size, num_workers = num_workers, pin_memory=True,
                                    drop_last=True, collate_fn=efficientdet_dataset_collate)
        gen_val         = DataLoader(val_dataset  , shuffle = True, batch_size = batch_size, num_workers = num_workers, pin_memory=True, 
                                    drop_last=True, collate_fn=efficientdet_dataset_collate)
                        
        epoch_step      = num_train // batch_size
        epoch_step_val  = num_val // batch_size
        
        if epoch_step == 0 or epoch_step_val == 0:
            raise ValueError("Dataset too small. Unable to train.")

        if Freeze_Train:
            for param in model.backbone_net.parameters():
                param.requires_grad = True
                
        for epoch in range(start_epoch, end_epoch):
            fit_one_epoch(model_train, model, focal_loss, loss_history, optimizer, epoch, 
                    epoch_step, epoch_step_val, gen, gen_val, end_epoch, Cuda)
            lr_scheduler.step()
