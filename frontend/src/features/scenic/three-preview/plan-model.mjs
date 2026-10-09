import * as data from './plan-data.mjs';
import {createCampus as renderExistingModels} from './calibrated-model.mjs';
export function createCampus(){return renderExistingModels(data);}
