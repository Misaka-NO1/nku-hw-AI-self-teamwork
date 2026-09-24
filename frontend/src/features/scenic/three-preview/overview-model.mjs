import * as data from './overview-data.mjs';
import {createCampus as renderCampus} from './calibrated-model.mjs';
export function createCampus(){return renderCampus(data);}
