import datetime
import yaml
import logging
import nvs
_log = logging.getLogger(__name__)

og1 = nvs.concept_dict_from_collection('OG1')
p02 = nvs.concept_dict_from_collection('P02')
p01 = nvs.concept_dict_from_collection('P01')
p06 = nvs.concept_dict_from_collection('P06')
og1_p01_p02 = p01 | p02 | og1
df_p07 = nvs.table_from_collection('P07')


def validate_variable(var_name, variable):
    """
    Validate the metadata from a variables used in the OceanGliders format against the NERC vocab server. Steps:
    1. Assign mandatory coordinates "TIME, LONGITUDE, LATITUDE, DEPTH"
    3. Check that all mandatory attributes are present
    4. Check that the vocabulary URI is present in the OG1, P02 or P02 collections
    5. Check that the standard_name is present in the P07 CF standard names vocab
    6. If long_name is missing, assign the value from P07 description with spaces replacing underscores
    7. Check units of the standard_name against the linked P06 entry CHECK CURRENTLY BYPASSED
    :param var_name: dictionary of variable attributes for OG1
    :param variable: name of variable (used for log messages)
    :return: dict of corrected variable attricubutes or False if a check fails
    """
    if var_name not in ["TIME", "LONGITUDE", "LATITUDE", "DEPTH"]:
        variable['coordinates'] =  "TIME, LONGITUDE, LATITUDE, DEPTH"
    mandatory_keys = {'vocabulary', 'units'}
    missing_keys =  mandatory_keys - set(variable.keys())
    if missing_keys:
        _log.error(f"expected keys {missing_keys} not found in {var_name}")
        return False

    if 'https:' in variable['vocabulary']:
        variable['vocabulary'].replace('https:', 'http:')
    if variable['vocabulary'][-1] != '/':
        variable['vocabulary'] += '/'
    if variable['vocabulary'] not in og1_p01_p02.keys():
        _log.error(f"{var_name} URI {variable['vocabulary']} not found on NVS. Check URI or log request to add")
        return False
    if 'standard_name' in variable.keys():
        standard_name =  variable['standard_name']
        if standard_name not in df_p07['cf_standard_name'].values:
            _log.error(f'{var_name} standard name {standard_name} not found in P07')
            return False
    concept = og1_p01_p02[variable['vocabulary']]
    if 'long_name' in variable.keys():
        if variable['long_name'] != concept['skos:prefLabel']['@value']:
            _log.warning(f"{var_name} long_name '{variable['long_name']}' does not match expected value from NVS '{concept['skos:prefLabel']['@value']}'")
    else:
        variable['long_name'] =  concept['skos:prefLabel']['@value']
    return variable
    units_uri = df_p07.loc[df_p07['cf_standard_name']==standard_name, 'units_uri'].values[0]
    # Get units directly from the concept if they are linked
    if 'skos:related' in concept.keys():
        related = concept['skos:related']
        if type(related) is dict:
            related = [related]
        for related_term in related:
            if 'P06' in related_term['@id']:
                units_uri = related_term['@id']
                break
    unit_dict = p06[units_uri]

    accepted_units = [unit_dict['skos:prefLabel']['@value'], unit_dict['skos:altLabel']]
    # skip unit check for now
    #if variable['units'] not in accepted_units:
    #    _log.error(f'{var_name} unit {variable["units"]} not in expected units {accepted_units} from {units_uri}')
    return variable


def validate_variables_from_yaml():
    validated_variables = {}
    input_variables = {}
    for input_file in ['yaml/draft_yaml/voto_variables.yaml', 'yaml/draft_yaml/og1_coordinates.yaml']:
        with open(input_file) as f:
            draft_variables = yaml.safe_load(f)
        input_variables = input_variables | draft_variables
        _log.info(f"START check {len(draft_variables)} variables")
        for var_name, variables in draft_variables.items():
            _log.debug(f'Validate {var_name}')
            validated = validate_variable(var_name, variables)
            if validated:
                validated_variables[var_name] = validated
    with open('yaml/validated_yaml/og1_variables.yaml', 'w') as f:
        yaml.safe_dump(validated_variables, f)
    _log.info(f"COMPLETE check all variables, read {len(input_variables)} unique variables, wrote {len(validated_variables)} variables")

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("variables_vocab.log", 'w'),
            logging.StreamHandler()
        ]
    )
    start = datetime.datetime.now()
    validate_variables_from_yaml()
    _log.info(f"COMPLETE in {datetime.datetime.now() - start}")