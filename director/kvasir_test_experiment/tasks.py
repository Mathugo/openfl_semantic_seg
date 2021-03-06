import torch
import numpy as np
import tqdm
from openfl.component.aggregation_functions import Median
from openfl.interface.interactive_api.experiment import TaskInterface

#CRITERION=torch.nn.MSELoss(reduction='mean')
class Task:
    """ Create task to train a federated agent """
    @staticmethod
    def createTask(loss_fn, val_fn, deeplab_model, aggregation_function=Median()):
        TI = TaskInterface()
        # The Interactive API supports registering functions definied in main module or imported.
        def function_defined_in_notebook(some_parameter):
            print(f'Also I accept a parameter and it is {some_parameter}')

        #The Interactive API supports overriding of the aggregation function

        # Task interface currently supports only standalone functions.
        @TI.add_kwargs(**{'loss_fn': loss_fn, 'deeplab_model': deeplab_model})
        @TI.register_fl_task(model='model', data_loader='train_loader', \
                            device='device', optimizer='optimizer')     
        @TI.set_aggregation_function(aggregation_function)
        def train(model, train_loader, optimizer, device, loss_fn, deeplab_model):
            # TODO we can tune the loss functon with the aux output and apply a coeff
            """    
            The following constructions, that may lead to resource race
            is no longer needed:
            
            if not torch.cuda.is_available():
                device = 'cpu'
            else:
                device = 'cuda'        
            """
            # we freeze the layers during the training (otherwise the opt don't load the model correctly afterwards)
            deeplab_model.freeze()

            print(f'\n\n TASK TRAIN GOT DEVICE {device}\n\n')
            
            #function_defined_in_notebook(some_parameter)
            
            train_loader = tqdm.tqdm(train_loader, desc="train")
            model.train()
            model.to(device)
            losses = []

            for data, target in train_loader:
                data, target = torch.tensor(data).to(device), torch.tensor(
                    target).to(device, dtype=torch.float32)

                optimizer.zero_grad()
                output = model(data)["out"]
                
                #loss = loss_fn().forward(output, target)
                loss = loss_fn(output=output, target=target)
                loss.backward()
                optimizer.step()
                losses.append(loss.detach().cpu().numpy())
            
            deeplab_model.unfreeze()

            return {'train_loss (dice loss)': np.mean(losses),}

        @TI.add_kwargs(**{'loss_fn': loss_fn, 'val_fn': val_fn})
        @TI.register_fl_task(model='model', data_loader='val_loader', device='device')     
        def validate(model, val_loader, device, loss_fn, val_fn):

            print(f'\n\n TASK VALIDATE GOT DEVICE {device}\n\n')
            model.eval()
            model.to(device)
            
            val_loader = tqdm.tqdm(val_loader, desc="validate")
            val_score = 0
            total_samples = 0

            with torch.no_grad():
                for data, target in val_loader:
                    samples = target.shape[0]
                    total_samples += samples
                    data, target = torch.tensor(data).to(device), \
                        torch.tensor(target).to(device, dtype=torch.int64)

                    output = model(data)["out"]
                    val = val_fn(output, target)
                    val_score += val.sum().cpu().numpy()

            return {'Val Score (Dice Coeff)': val_score / total_samples,}
        
        return TI, validate