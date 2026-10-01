# Astra token diagnosis packet

Independent forensic review only. GPT-6 Astra did not run as an experimental arm and this packet is not evidence that any claim passes. Do not inspect, tune against, or run the reserved validation cohort.

Spec SHA-256: `9acaec8ccdb6a51161eeee6488059b043d0a92893a0ba0a5b907fd7c67f5e0d4`. Product RC hashes and exact design are in `token_claim_discovery/preregistered_spec.json`, `exact_notes.json`, `helper_schemas.json`, `arm_configs.json`, `selection_manifest.json`, and `run_order.json`.

The exact notes are:

```text
NEUTRAL: ## Working note
Use the available spreadsheet tools as appropriate for the task. Check the workbook and produce the requested output. Continue until you can submit the result. Record the final output path.
SALIENCE: ## Working note
Prefer targeted inspection of needed cells or ranges using ordinary Python/openpyxl. Avoid dumping entire workbooks or sheets unless broad inspection is required. Gather evidence incrementally.
HELPERS ON: ## Optional factual helpers
You may import `lx_helpers` in Python. Available signatures: `search(workbook, pattern, regex=False, sheet=None)`, `periods(workbook, sheet=None)`, `inspect(workbook, sheet, cell_range, with_styles=False)`. These read the workbook with ordinary openpyxl. They are optional; ordinary Python/openpyxl and view_xlsx remain available.
```

Population: `['Template:16_07', 'Template:06_02', 'Template:16_08', 'Template:01_05', 'Template:04_04', 'Financial_Model:02_04', 'Financial_Model:18_05', 'Financial_Model:02_05', 'Financial_Model:15_03', 'Financial_Model:09_02', 'Debugging:04_07', 'Debugging:07_05', 'Debugging:09_03', 'Debugging:06_10', 'Debugging:01_04']`. Primary slots: 60/60. Replications: 0. Censoring: `{'A': {'MODEL_NONCOMPLETION': 4, 'PROVIDER_CENSORED': 1, 'VALID_SUBMISSION': 10}, 'B': {'MODEL_NONCOMPLETION': 3, 'VALID_SUBMISSION': 12}, 'C': {'MODEL_NONCOMPLETION': 5, 'PROVIDER_CENSORED': 2, 'VALID_SUBMISSION': 8}, 'D': {'MODEL_NONCOMPLETION': 5, 'PROVIDER_CENSORED': 1, 'VALID_SUBMISSION': 9}}`. Primary verdict: `TOKEN_EFFECT_TRAJECTORY_NOISE`.

The provider tool schemas are identical in all arms: see `helper_schemas.json`. The helper factor is the frozen Python module, import availability, and exact signature addendum. This is a possible limitation for a claim about directly exposed tool schemas.

## Task-level token table

| Task | A | B | C | D |
| --- | ---: | ---: | ---: | ---: |
| Template:16_07 | 68,819 | 55,568 | 56,086 | 55,831 |
| Template:06_02 | 36,509 | 25,312 | 827,565 | 86,100 |
| Template:16_08 | 4,812 | 16,261 | 8,052 | 16,692 |
| Template:01_05 | 150,528 | 54,527 | 151,637 | 43,978 |
| Template:04_04 | 191,814 | 26,604 | 19,391 | 24,153 |
| Financial_Model:02_04 | 98,268 | 104,378 | 76,684 | 202,754 |
| Financial_Model:18_05 | 151,902 | 135,044 | 114,856 | 103,132 |
| Financial_Model:02_05 | 88,722 | 104,004 | 103,066 | 97,842 |
| Financial_Model:15_03 | 1,682,032 | 1,682,757 | 1,635,616 | 1,214,042 |
| Financial_Model:09_02 | 356,349 | 216,098 | 190,956 | 344,038 |
| Debugging:04_07 | 1,229,271 | 667,037 | 1,595,231 | 902,434 |
| Debugging:07_05 | 675,750 | 295,103 | 217,940 | 949,105 |
| Debugging:09_03 | 1,422,888 | 1,345,963 | 1,605,088 | 1,124,509 |
| Debugging:06_10 | 646,091 | 921,654 | 325,521 | 908,078 |
| Debugging:01_04 | 1,154,739 | 1,462,459 | 1,412,769 | 1,464,470 |

## Contrasts, capability, mechanism, and contradictions

```json
{
  "factorial": {
    "contrasts": {
      "B_vs_A": {
        "E1_dual_valid": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.37548195322790373,
            0.8401117250895858
          ],
          "geometric_mean_ratio": 0.5867674355586094,
          "mean_ratio": 0.6853627948435468,
          "median_ratio": 0.6933084992741516,
          "median_reduction_pct": 30.669150072584838,
          "n": 9,
          "treatment_higher_count": 2,
          "treatment_lower_count": 7
        },
        "E2_all_uncensored": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.50162020386776,
            0.9388129922794695
          ],
          "geometric_mean_ratio": 0.7060411233564814,
          "mean_ratio": 0.8107324428122057,
          "median_ratio": 0.8482359916445084,
          "median_reduction_pct": 15.176400835549163,
          "n": 14,
          "treatment_higher_count": 5,
          "treatment_lower_count": 9
        },
        "family": {
          "Debugging": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.5559662447057085,
              1.2234528712145378
            ],
            "geometric_mean_ratio": 0.8346132400531769,
            "mean_ratio": 0.9236524844024372,
            "median_ratio": 0.9459374174214695,
            "median_reduction_pct": 5.406258257853047,
            "n": 5,
            "treatment_higher_count": 2,
            "treatment_lower_count": 3
          },
          "Financial_Model": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.7408665427452086,
              1.0917511540971885
            ],
            "geometric_mean_ratio": 0.9234596966836156,
            "mean_ratio": 0.9460593460515616,
            "median_ratio": 1.0004310262824965,
            "median_reduction_pct": -0.04310262824964717,
            "n": 5,
            "treatment_higher_count": 3,
            "treatment_lower_count": 2
          },
          "Template": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.20738703804006356,
              0.748206481902727
            ],
            "geometric_mean_ratio": 0.40952080533770174,
            "mean_ratio": 0.5004237617752215,
            "median_ratio": 0.5277733769755112,
            "median_reduction_pct": 47.22266230244888,
            "n": 4,
            "treatment_higher_count": 0,
            "treatment_lower_count": 4
          }
        },
        "task_pairs": [
          {
            "dual_valid": true,
            "log_ratio": -0.2138723736023531,
            "ratio": 0.8074514305642337,
            "task": "Template:16_07"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.36628021395096466,
            "ratio": 0.6933084992741516,
            "task": "Template:06_02"
          },
          {
            "dual_valid": true,
            "log_ratio": -1.0154531215592448,
            "ratio": 0.36223825467687076,
            "task": "Template:01_05"
          },
          {
            "dual_valid": true,
            "log_ratio": -1.9754645720640556,
            "ratio": 0.13869686258562983,
            "task": "Template:04_04"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.060320485196879964,
            "ratio": 1.0621769039768796,
            "task": "Financial_Model:02_04"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.11763492480995542,
            "ratio": 0.8890205527247831,
            "task": "Financial_Model:18_05"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.1589214743208027,
            "ratio": 1.1722458916615945,
            "task": "Financial_Model:02_05"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.00043093341735229063,
            "ratio": 1.0004310262824965,
            "task": "Financial_Model:15_03"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.5001785792186481,
            "ratio": 0.6064223556120545,
            "task": "Financial_Model:09_02"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.6113310730927167,
            "ratio": 0.5426281104817408,
            "task": "Debugging:04_07"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.8284987372139287,
            "ratio": 0.4367044025157233,
            "task": "Debugging:07_05"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.05557886706418617,
            "ratio": 0.9459374174214695,
            "task": "Debugging:09_03"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.35522952124021945,
            "ratio": 1.4265080306025002,
            "task": "Debugging:06_10"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.23624492113106949,
            "ratio": 1.266484460990752,
            "task": "Debugging:01_04"
          }
        ]
      },
      "C_vs_A": {
        "E1_dual_valid": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.307566429901834,
            0.8711787649257257
          ],
          "geometric_mean_ratio": 0.5568421885016471,
          "mean_ratio": 0.6809917693138697,
          "median_ratio": 0.7682374192837298,
          "median_reduction_pct": 23.17625807162702,
          "n": 8,
          "treatment_higher_count": 2,
          "treatment_lower_count": 6
        },
        "E2_all_uncensored": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.5165075340540984,
            1.8229465046496538
          ],
          "geometric_mean_ratio": 0.9253859512377245,
          "mean_ratio": 2.5182285272737355,
          "median_ratio": 0.9724048056160643,
          "median_reduction_pct": 2.759519438393565,
          "n": 13,
          "treatment_higher_count": 6,
          "treatment_lower_count": 7
        },
        "family": {
          "Debugging": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.4603679315665866,
              1.2324546086319441
            ],
            "geometric_mean_ratio": 0.781241890082018,
            "mean_ratio": 0.8951109301270477,
            "median_ratio": 1.1280494318597107,
            "median_reduction_pct": -12.804943185971073,
            "n": 5,
            "treatment_higher_count": 3,
            "treatment_lower_count": 2
          },
          "Financial_Model": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.7681418346650066,
              1.0628343873205293
            ],
            "geometric_mean_ratio": 0.9035527412505866,
            "mean_ratio": 0.9176382965646925,
            "median_ratio": 0.8763802837051706,
            "median_reduction_pct": 12.361971629482937,
            "n": 4,
            "treatment_higher_count": 1,
            "treatment_lower_count": 3
          },
          "Template": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.17961264208738056,
              9.870477445825648
            ],
            "geometric_mean_ratio": 1.1711540403098795,
            "mean_ratio": 6.147715754416138,
            "median_ratio": 0.911172910870922,
            "median_reduction_pct": 8.8827089129078,
            "n": 4,
            "treatment_higher_count": 2,
            "treatment_lower_count": 2
          }
        },
        "task_pairs": [
          {
            "dual_valid": true,
            "log_ratio": -0.2045936425864947,
            "ratio": 0.8149784216568099,
            "task": "Template:16_07"
          },
          {
            "dual_valid": false,
            "log_ratio": 3.1209288484790747,
            "ratio": 22.667424470678462,
            "task": "Template:06_02"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.007340393358149251,
            "ratio": 1.0073674000850341,
            "task": "Template:01_05"
          },
          {
            "dual_valid": true,
            "log_ratio": -2.2917171115857493,
            "ratio": 0.10109272524424703,
            "task": "Template:04_04"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.2480053584182485,
            "ratio": 0.7803557617942769,
            "task": "Financial_Model:02_04"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.27955640624660144,
            "ratio": 0.7561190767731827,
            "task": "Financial_Model:18_05"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.14986167409952814,
            "ratio": 1.1616735420752462,
            "task": "Financial_Model:02_05"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.027983094536682872,
            "ratio": 0.9724048056160643,
            "task": "Financial_Model:15_03"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.26059724258497013,
            "ratio": 1.2977048998959546,
            "task": "Debugging:04_07"
          },
          {
            "dual_valid": true,
            "log_ratio": -1.1316033896078168,
            "ratio": 0.32251572327044026,
            "task": "Debugging:07_05"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.1204899746863519,
            "ratio": 1.1280494318597107,
            "task": "Debugging:09_03"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.6855133850382803,
            "ratio": 0.5038315036117204,
            "task": "Debugging:06_10"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.20167726397266286,
            "ratio": 1.2234530919974125,
            "task": "Debugging:01_04"
          }
        ]
      },
      "D_vs_A": {
        "E1_dual_valid": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.38807448073869144,
            1.3587849483444203
          ],
          "geometric_mean_ratio": 0.7544603477692502,
          "mean_ratio": 1.049766482541116,
          "median_ratio": 0.8883627286027507,
          "median_reduction_pct": 11.163727139724934,
          "n": 8,
          "treatment_higher_count": 3,
          "treatment_lower_count": 5
        },
        "E2_all_uncensored": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.5631591639611041,
            1.2119890703056515
          ],
          "geometric_mean_ratio": 0.8541678593824318,
          "mean_ratio": 1.0516119295279458,
          "median_ratio": 0.8883627286027507,
          "median_reduction_pct": 11.163727139724934,
          "n": 14,
          "treatment_higher_count": 6,
          "treatment_lower_count": 8
        },
        "family": {
          "Debugging": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.8434577673204676,
              1.3765195917552413
            ],
            "geometric_mean_ratio": 1.0775138706925111,
            "mean_ratio": 1.1205328209422545,
            "median_ratio": 1.2682259800699551,
            "median_reduction_pct": -26.822598006995513,
            "n": 5,
            "treatment_higher_count": 3,
            "treatment_lower_count": 2
          },
          "Financial_Model": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.7465139646033632,
              1.4574685009398058
            ],
            "geometric_mean_ratio": 1.0148510783297167,
            "mean_ratio": 1.1064460250497512,
            "median_ratio": 0.9654524076116392,
            "median_reduction_pct": 3.4547592388360804,
            "n": 5,
            "treatment_higher_count": 2,
            "treatment_lower_count": 3
          },
          "Template": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.1918025962267681,
              1.3991264160074817
            ],
            "geometric_mean_ratio": 0.5150742115968152,
            "mean_ratio": 0.8969181958578032,
            "median_ratio": 0.5517156595758427,
            "median_reduction_pct": 44.82843404241573,
            "n": 4,
            "treatment_higher_count": 1,
            "treatment_lower_count": 3
          }
        },
        "task_pairs": [
          {
            "dual_valid": true,
            "log_ratio": -0.20915059892510607,
            "ratio": 0.8112730495938621,
            "task": "Template:16_07"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.857950605897477,
            "ratio": 2.3583226053849735,
            "task": "Template:06_02"
          },
          {
            "dual_valid": true,
            "log_ratio": -1.2304596045194733,
            "ratio": 0.29215826955782315,
            "task": "Template:01_05"
          },
          {
            "dual_valid": true,
            "log_ratio": -2.072117556500277,
            "ratio": 0.1259188588945541,
            "task": "Template:04_04"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.7242949814548248,
            "ratio": 2.0632759392681237,
            "task": "Financial_Model:02_04"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.3872258549329311,
            "ratio": 0.6789377361720056,
            "task": "Financial_Model:18_05"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.09784604708778973,
            "ratio": 1.1027929938459458,
            "task": "Financial_Model:02_05"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.3260472979255738,
            "ratio": 0.7217710483510421,
            "task": "Financial_Model:15_03"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.03515847132525624,
            "ratio": 0.9654524076116392,
            "task": "Financial_Model:09_02"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.30908103239469215,
            "ratio": 0.734121280010673,
            "task": "Debugging:04_07"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.3396962501147853,
            "ratio": 1.4045209027007028,
            "task": "Debugging:07_05"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.2353421131106858,
            "ratio": 0.7903004312356279,
            "task": "Debugging:09_03"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.3403899172606745,
            "ratio": 1.4054955106943139,
            "task": "Debugging:06_10"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.23761905785692755,
            "ratio": 1.2682259800699551,
            "task": "Debugging:01_04"
          }
        ]
      },
      "D_vs_B": {
        "E1_dual_valid": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.946114143310999,
            1.7335136007958474
          ],
          "geometric_mean_ratio": 1.2513311878764475,
          "mean_ratio": 1.412508451104305,
          "median_ratio": 1.00473293982148,
          "median_reduction_pct": -0.4732939821479931,
          "n": 9,
          "treatment_higher_count": 5,
          "treatment_lower_count": 4
        },
        "E2_all_uncensored": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.9543354535258894,
            1.5867433360713012
          ],
          "geometric_mean_ratio": 1.2097990203768356,
          "mean_ratio": 1.3908808083248743,
          "median_ratio": 0.9933225207974077,
          "median_reduction_pct": 0.6677479202592318,
          "n": 14,
          "treatment_higher_count": 7,
          "treatment_lower_count": 7
        },
        "family": {
          "Debugging": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.9253656588988356,
              2.065586801307008
            ],
            "geometric_mean_ratio": 1.291033761486767,
            "mean_ratio": 1.47823892817246,
            "median_ratio": 1.00137508128433,
            "median_reduction_pct": -0.13750812843300597,
            "n": 5,
            "treatment_higher_count": 3,
            "treatment_lower_count": 2
          },
          "Financial_Model": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.7783003696800037,
              1.5517491153511571
            ],
            "geometric_mean_ratio": 1.098966291625191,
            "mean_ratio": 1.1920895710074624,
            "median_ratio": 0.9407522787585093,
            "median_reduction_pct": 5.924772124149069,
            "n": 5,
            "treatment_higher_count": 2,
            "treatment_lower_count": 3
          },
          "Template": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.8520803760198915,
              2.4449138051237
            ],
            "geometric_mean_ratio": 1.2577485804953705,
            "mean_ratio": 1.530172205162157,
            "median_ratio": 0.95630196833203,
            "median_reduction_pct": 4.369803166797004,
            "n": 4,
            "treatment_higher_count": 2,
            "treatment_lower_count": 2
          }
        },
        "task_pairs": [
          {
            "dual_valid": true,
            "log_ratio": 0.00472177467724701,
            "ratio": 1.00473293982148,
            "task": "Template:16_07"
          },
          {
            "dual_valid": true,
            "log_ratio": 1.2242308198484417,
            "ratio": 3.4015486725663715,
            "task": "Template:06_02"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.21500648296022845,
            "ratio": 0.8065362114181965,
            "task": "Template:01_05"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.09665298443622129,
            "ratio": 0.9078709968425801,
            "task": "Template:04_04"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.663974496257945,
            "ratio": 1.9424974611508172,
            "task": "Financial_Model:02_04"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.2695909301229755,
            "ratio": 0.7636918337726963,
            "task": "Financial_Model:18_05"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.061075427233013034,
            "ratio": 0.9407522787585093,
            "task": "Financial_Model:02_05"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.3264782313429261,
            "ratio": 0.7214600800947493,
            "task": "Financial_Model:15_03"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.4650201078933918,
            "ratio": 1.5920462012605392,
            "task": "Financial_Model:09_02"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.3022500406980245,
            "ratio": 1.352899464347555,
            "task": "Debugging:04_07"
          },
          {
            "dual_valid": false,
            "log_ratio": 1.1681949873287143,
            "ratio": 3.2161821465725526,
            "task": "Debugging:07_05"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.17976324604649976,
            "ratio": 0.8354679883473766,
            "task": "Debugging:09_03"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.014839603979544922,
            "ratio": 0.9852699603104853,
            "task": "Debugging:06_10"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.001374136725858103,
            "ratio": 1.00137508128433,
            "task": "Debugging:01_04"
          }
        ]
      },
      "D_vs_C": {
        "E1_dual_valid": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.5439411313705074,
            1.5968806536920617
          ],
          "geometric_mean_ratio": 0.9655825421479821,
          "mean_ratio": 1.1703851371803464,
          "median_ratio": 0.9723837213094104,
          "median_reduction_pct": 2.761627869058958,
          "n": 6,
          "treatment_higher_count": 2,
          "treatment_lower_count": 4
        },
        "E2_all_uncensored": {
          "bootstrap_95pct_ci_geometric_ratio": [
            0.5353727344503874,
            1.4900096108089163
          ],
          "geometric_mean_ratio": 0.914384733637239,
          "mean_ratio": 1.332000252501585,
          "median_ratio": 0.9493140317854578,
          "median_reduction_pct": 5.068596821454219,
          "n": 13,
          "treatment_higher_count": 5,
          "treatment_lower_count": 8
        },
        "family": {
          "Debugging": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.6955754528261228,
              2.7643182122861125
            ],
            "geometric_mean_ratio": 1.37923207187391,
            "mean_ratio": 1.8894797220786421,
            "median_ratio": 1.0365955085367813,
            "median_reduction_pct": -3.6595508536781285,
            "n": 5,
            "treatment_higher_count": 3,
            "treatment_lower_count": 2
          },
          "Financial_Model": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.7893447884994332,
              2.01840559983354
            ],
            "geometric_mean_ratio": 1.1372780878386475,
            "mean_ratio": 1.308377921303721,
            "median_ratio": 0.9236191946208754,
            "median_reduction_pct": 7.638080537912462,
            "n": 4,
            "treatment_higher_count": 1,
            "treatment_lower_count": 3
          },
          "Template": {
            "bootstrap_95pct_ci_geometric_ratio": [
              0.17370633764791518,
              1.1135145776567674
            ],
            "geometric_mean_ratio": 0.43980056753296953,
            "mean_ratio": 0.658773246728128,
            "median_ratio": 0.6427374877455326,
            "median_reduction_pct": 35.72625122544674,
            "n": 4,
            "treatment_higher_count": 1,
            "treatment_lower_count": 3
          }
        },
        "task_pairs": [
          {
            "dual_valid": true,
            "log_ratio": -0.0045569563386113595,
            "ratio": 0.995453410833363,
            "task": "Template:16_07"
          },
          {
            "dual_valid": false,
            "log_ratio": -2.2629782425815974,
            "ratio": 0.1040401660292545,
            "task": "Template:06_02"
          },
          {
            "dual_valid": true,
            "log_ratio": -1.2377999978776226,
            "ratio": 0.2900215646577023,
            "task": "Template:01_05"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.21959955508547238,
            "ratio": 1.2455778453921922,
            "task": "Template:04_04"
          },
          {
            "dual_valid": true,
            "log_ratio": 0.9723003398730735,
            "ratio": 2.6440196129570706,
            "task": "Financial_Model:02_04"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.10766944868632966,
            "ratio": 0.8979243574562931,
            "task": "Financial_Model:18_05"
          },
          {
            "dual_valid": true,
            "log_ratio": -0.05201562701173853,
            "ratio": 0.9493140317854578,
            "task": "Financial_Model:02_05"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.298064203388891,
            "ratio": 0.7422536830160624,
            "task": "Financial_Model:15_03"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.5696782749796624,
            "ratio": 0.5657074116538607,
            "task": "Debugging:04_07"
          },
          {
            "dual_valid": false,
            "log_ratio": 1.4712996397226024,
            "ratio": 4.354891254473708,
            "task": "Debugging:07_05"
          },
          {
            "dual_valid": false,
            "log_ratio": -0.35583208779703773,
            "ratio": 0.700590248011324,
            "task": "Debugging:09_03"
          },
          {
            "dual_valid": false,
            "log_ratio": 1.025903302298955,
            "ratio": 2.789614187717536,
            "task": "Debugging:06_10"
          },
          {
            "dual_valid": false,
            "log_ratio": 0.03594179388426477,
            "ratio": 1.0365955085367813,
            "task": "Debugging:01_04"
          }
        ]
      }
    },
    "family_effects_with_ci": {
      "Debugging": {
        "H_at_S0": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.5870476975354947,
            0.2016770835138484
          ],
          "mean_log_effect": -0.18078684699990824,
          "multiplicative_ratio": 0.8346132400531772,
          "n": 5
        },
        "H_at_S1": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.36301578633382653,
            1.016794026733945
          ],
          "mean_log_effect": 0.32152687462582463,
          "multiplicative_ratio": 1.3792320718739102,
          "n": 5
        },
        "S_at_H0": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.7757292579778146,
            0.20900779756032328
          ],
          "mean_log_effect": -0.2468704586804229,
          "multiplicative_ratio": 0.7812418900820177,
          "n": 5
        },
        "S_at_H1": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.07756631266524608,
            0.7254143513275324
          ],
          "mean_log_effect": 0.25544326294530995,
          "multiplicative_ratio": 1.2910337614867664,
          "n": 5
        },
        "interaction": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.19189197956925205,
            1.473953156924305
          ],
          "mean_log_effect": 0.5023137216257328,
          "multiplicative_ratio": 1.6525403692206377,
          "n": 5
        }
      },
      "Financial_Model": {
        "H_at_S0": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.07314607230824643,
            0.11929883909493988
          ],
          "mean_log_effect": 0.025509492031269954,
          "multiplicative_ratio": 1.0258376435072214,
          "n": 4
        },
        "H_at_S1": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.2365520592946031,
            0.7023078927332231
          ],
          "mean_log_effect": 0.1286377651965287,
          "multiplicative_ratio": 1.1372780878386475,
          "n": 4
        },
        "S_at_H0": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.26378088233242547,
            0.060939289781423156
          ],
          "mean_log_effect": -0.10142079627550116,
          "multiplicative_ratio": 0.9035527412505866,
          "n": 4
        },
        "S_at_H1": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.29803458073295097,
            0.4305831396627142
          ],
          "mean_log_effect": 0.0017074768897575865,
          "multiplicative_ratio": 1.0017089354584614,
          "n": 4
        },
        "interaction": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.25471611906939184,
            0.6312506156740101
          ],
          "mean_log_effect": 0.10312827316525874,
          "multiplicative_ratio": 1.108633607897663,
          "n": 4
        }
      },
      "Template": {
        "H_at_S0": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -1.5731684825357823,
            -0.2900762937766581
          ],
          "mean_log_effect": -0.8927675702941542,
          "multiplicative_ratio": 0.40952080533770185,
          "n": 4
        },
        "H_at_S1": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -1.7503891202296105,
            0.10752129937343025
          ],
          "mean_log_effect": -0.8214339104280901,
          "multiplicative_ratio": 0.4398005675329694,
          "n": 4
        },
        "S_at_H0": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -1.7169527353497744,
            2.2895482257126827
          ],
          "mean_log_effect": 0.15798962191624533,
          "multiplicative_ratio": 1.17115404030988,
          "n": 4
        },
        "S_at_H1": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -0.16007441855085958,
            0.8940098687772746
          ],
          "mean_log_effect": 0.22932328178230943,
          "multiplicative_ratio": 1.25774858049537,
          "n": 4
        },
        "interaction": {
          "bootstrap_95pct_ci_mean_log_effect": [
            -1.3701946671570404,
            1.5907113762825507
          ],
          "mean_log_effect": 0.0713336598660641,
          "multiplicative_ratio": 1.0739394966033484,
          "n": 4
        }
      }
    },
    "overall_effects_with_ci": {
      "H_at_S0": {
        "bootstrap_95pct_ci_mean_log_effect": [
          -0.6894249017830323,
          -0.04009212438875815
        ],
        "mean_log_effect": -0.33638204215777523,
        "multiplicative_ratio": 0.7143501418079147,
        "n": 13
      },
      "H_at_S1": {
        "bootstrap_95pct_ci_mean_log_effect": [
          -0.62479207476158,
          0.39878257014389185
        ],
        "mean_log_effect": -0.08950386213824019,
        "multiplicative_ratio": 0.914384733637239,
        "n": 13
      },
      "S_at_H0": {
        "bootstrap_95pct_ci_mean_log_effect": [
          -0.6606654037832373,
          0.6004541505866724
        ],
        "mean_log_effect": -0.07754438391070291,
        "multiplicative_ratio": 0.9253859512377245,
        "n": 13
      },
      "S_at_H1": {
        "bootstrap_95pct_ci_mean_log_effect": [
          -0.08161617920162047,
          0.4563050875931624
        ],
        "mean_log_effect": 0.16933379610883215,
        "multiplicative_ratio": 1.184515459593312,
        "n": 13
      },
      "interaction": {
        "bootstrap_95pct_ci_mean_log_effect": [
          -0.31186822487851357,
          0.8293788543157485
        ],
        "mean_log_effect": 0.24687818001953504,
        "multiplicative_ratio": 1.280023170882372,
        "n": 13
      }
    },
    "overall_mean_log_effects": {
      "H_at_S0": -0.33638204215777523,
      "H_at_S1": -0.08950386213824019,
      "S_at_H0": -0.07754438391070291,
      "S_at_H1": 0.16933379610883215,
      "interaction": 0.24687818001953504
    },
    "task_level_log_effects": [
      {
        "H_at_S0": -0.2138723736023529,
        "H_at_S1": -0.0045569563386109735,
        "S_at_H0": -0.20459364258649337,
        "S_at_H1": 0.004721774677248547,
        "family": "Template",
        "interaction": 0.20931541726374192,
        "task": "Template:16_07"
      },
      {
        "H_at_S0": -0.36628021395096333,
        "H_at_S1": -2.262978242581598,
        "S_at_H0": 3.1209288484790747,
        "S_at_H1": 1.2242308198484402,
        "family": "Template",
        "interaction": -1.8966980286306345,
        "task": "Template:06_02"
      },
      {
        "H_at_S0": -1.0154531215592453,
        "H_at_S1": -1.237799997877623,
        "S_at_H0": 0.0073403933581488445,
        "S_at_H1": -0.21500648296022895,
        "family": "Template",
        "interaction": -0.2223468763183778,
        "task": "Template:01_05"
      },
      {
        "H_at_S0": -1.9754645720640553,
        "H_at_S1": 0.21959955508547147,
        "S_at_H0": -2.291717111585749,
        "S_at_H1": -0.09665298443622206,
        "family": "Template",
        "interaction": 2.195064127149527,
        "task": "Template:04_04"
      },
      {
        "H_at_S0": 0.060320485196880824,
        "H_at_S1": 0.9723003398730743,
        "S_at_H0": -0.2480053584182489,
        "S_at_H1": 0.6639744962579446,
        "family": "Financial_Model",
        "interaction": 0.9119798546761935,
        "task": "Financial_Model:02_04"
      },
      {
        "H_at_S0": -0.11763492480995552,
        "H_at_S1": -0.10766944868633033,
        "S_at_H0": -0.27955640624660205,
        "S_at_H1": -0.26959093012297686,
        "family": "Financial_Model",
        "interaction": 0.009965476123625194,
        "task": "Financial_Model:18_05"
      },
      {
        "H_at_S0": 0.1589214743208025,
        "H_at_S1": -0.052015627011737564,
        "S_at_H0": 0.14986167409952778,
        "S_at_H1": -0.06107542723301229,
        "family": "Financial_Model",
        "interaction": -0.21093710133254007,
        "task": "Financial_Model:02_05"
      },
      {
        "H_at_S0": 0.0004309334173520085,
        "H_at_S1": -0.2980642033888916,
        "S_at_H0": -0.027983094536681463,
        "S_at_H1": -0.3264782313429251,
        "family": "Financial_Model",
        "interaction": -0.2984951368062436,
        "task": "Financial_Model:15_03"
      },
      {
        "H_at_S0": -0.6113310730927157,
        "H_at_S1": -0.5696782749796618,
        "S_at_H0": 0.26059724258496964,
        "S_at_H1": 0.3022500406980235,
        "family": "Debugging",
        "interaction": 0.04165279811305389,
        "task": "Debugging:04_07"
      },
      {
        "H_at_S0": -0.8284987372139287,
        "H_at_S1": 1.4712996397226021,
        "S_at_H0": -1.1316033896078181,
        "S_at_H1": 1.1681949873287127,
        "family": "Debugging",
        "interaction": 2.299798376936531,
        "task": "Debugging:07_05"
      },
      {
        "H_at_S0": -0.05557886706418458,
        "H_at_S1": -0.3558320877970367,
        "S_at_H0": 0.12048997468635214,
        "S_at_H1": -0.17976324604649996,
        "family": "Debugging",
        "interaction": -0.3002532207328521,
        "task": "Debugging:09_03"
      },
      {
        "H_at_S0": 0.35522952124021856,
        "H_at_S1": 1.0259033022989552,
        "S_at_H0": -0.6855133850382806,
        "S_at_H1": -0.01483960397954398,
        "family": "Debugging",
        "interaction": 0.6706737810587367,
        "task": "Debugging:06_10"
      },
      {
        "H_at_S0": 0.23624492113106932,
        "H_at_S1": 0.03594179388426433,
        "S_at_H0": 0.2016772639726625,
        "S_at_H1": 0.001374136725857511,
        "family": "Debugging",
        "interaction": -0.200303127246805,
        "task": "Debugging:01_04"
      }
    ]
  },
  "capability": {
    "completion_discordance_D_vs_A": [
      "Debugging:04_07",
      "Debugging:07_05",
      "Debugging:06_10"
    ],
    "formal_equivalence": "NOT_ESTABLISHED",
    "mean_modification_valid_only": {
      "A": 0.70118,
      "B": 0.68875,
      "C": 0.6910375,
      "D": 0.8361888888888889
    },
    "mean_regression_valid_only": {
      "A": 0.97923,
      "B": 0.9798,
      "C": 0.98825,
      "D": 0.994
    },
    "paired_score_deltas": {
      "B_vs_A": {
        "mean_modification_delta": 0.018255555555555556,
        "mean_regression_delta": 0.0017888888888888893,
        "n": 9,
        "pairs": [
          {
            "modification_delta": 0.10749999999999998,
            "regression_delta": 0.0040000000000000036,
            "task": "Template:16_07"
          },
          {
            "modification_delta": 0.0,
            "regression_delta": 0.0,
            "task": "Template:06_02"
          },
          {
            "modification_delta": -0.32,
            "regression_delta": -0.039000000000000035,
            "task": "Template:01_05"
          },
          {
            "modification_delta": 0.0,
            "regression_delta": 0.029000000000000026,
            "task": "Template:04_04"
          },
          {
            "modification_delta": 0.0036000000000000476,
            "regression_delta": 0.0,
            "task": "Financial_Model:02_04"
          },
          {
            "modification_delta": 0.3376,
            "regression_delta": 0.0,
            "task": "Financial_Model:18_05"
          },
          {
            "modification_delta": 0.035599999999999965,
            "regression_delta": 0.0,
            "task": "Financial_Model:02_05"
          },
          {
            "modification_delta": 0.0,
            "regression_delta": 0.0,
            "task": "Financial_Model:09_02"
          },
          {
            "modification_delta": 0.0,
            "regression_delta": 0.02210000000000001,
            "task": "Debugging:07_05"
          }
        ]
      },
      "C_vs_A": {
        "mean_modification_delta": 0.06456250000000002,
        "mean_regression_delta": 0.014212500000000003,
        "n": 8,
        "pairs": [
          {
            "modification_delta": 0.4298,
            "regression_delta": 0.09040000000000004,
            "task": "Template:16_07"
          },
          {
            "modification_delta": -0.08000000000000007,
            "regression_delta": -0.03410000000000002,
            "task": "Template:01_05"
          },
          {
            "modification_delta": 0.08330000000000004,
            "regression_delta": 0.03620000000000001,
            "task": "Template:04_04"
          },
          {
            "modification_delta": -0.0034999999999999476,
            "regression_delta": 0.0,
            "task": "Financial_Model:02_04"
          },
          {
            "modification_delta": 0.044600000000000084,
            "regression_delta": 0.0,
            "task": "Financial_Model:18_05"
          },
          {
            "modification_delta": 0.035599999999999965,
            "regression_delta": 0.0,
            "task": "Financial_Model:02_05"
          },
          {
            "modification_delta": 0.0,
            "regression_delta": 0.021199999999999997,
            "task": "Debugging:07_05"
          },
          {
            "modification_delta": 0.006700000000000039,
            "regression_delta": 0.0,
            "task": "Debugging:06_10"
          }
        ]
      },
      "D_vs_A": {
        "mean_modification_delta": 0.0449,
        "mean_regression_delta": 0.0157625,
        "n": 8,
        "pairs": [
          {
            "modification_delta": 0.5951,
            "regression_delta": 0.08250000000000002,
            "task": "Template:16_07"
          },
          {
            "modification_delta": 0.0,
            "regression_delta": 0.0,
            "task": "Template:06_02"
          },
          {
            "modification_delta": -0.2,
            "regression_delta": 0.014599999999999946,
            "task": "Template:01_05"
          },
          {
            "modification_delta": -0.11119999999999997,
            "regression_delta": 0.029000000000000026,
            "task": "Template:04_04"
          },
          {
            "modification_delta": 0.0,
            "regression_delta": 0.0,
            "task": "Financial_Model:02_04"
          },
          {
            "modification_delta": 0.025500000000000078,
            "regression_delta": 0.0,
            "task": "Financial_Model:18_05"
          },
          {
            "modification_delta": 0.049799999999999955,
            "regression_delta": 0.0,
            "task": "Financial_Model:02_05"
          },
          {
            "modification_delta": 0.0,
            "regression_delta": 0.0,
            "task": "Financial_Model:09_02"
          }
        ]
      },
      "D_vs_C": {
        "mean_modification_delta": -0.0251,
        "mean_regression_delta": 0.005599999999999994,
        "n": 6,
        "pairs": [
          {
            "modification_delta": 0.1653,
            "regression_delta": -0.007900000000000018,
            "task": "Template:16_07"
          },
          {
            "modification_delta": -0.11999999999999994,
            "regression_delta": 0.048699999999999966,
            "task": "Template:01_05"
          },
          {
            "modification_delta": -0.1945,
            "regression_delta": -0.007199999999999984,
            "task": "Template:04_04"
          },
          {
            "modification_delta": 0.0034999999999999476,
            "regression_delta": 0.0,
            "task": "Financial_Model:02_04"
          },
          {
            "modification_delta": -0.019100000000000006,
            "regression_delta": 0.0,
            "task": "Financial_Model:18_05"
          },
          {
            "modification_delta": 0.01419999999999999,
            "regression_delta": 0.0,
            "task": "Financial_Model:02_05"
          }
        ]
      }
    },
    "submitted": {
      "A": 10,
      "B": 12,
      "C": 8,
      "D": 9
    },
    "valid": {
      "A": 10,
      "B": 12,
      "C": 8,
      "D": 9
    }
  },
  "censoring": {
    "by_arm": {
      "A": {
        "MODEL_NONCOMPLETION": 4,
        "PROVIDER_CENSORED": 1,
        "VALID_SUBMISSION": 10
      },
      "B": {
        "MODEL_NONCOMPLETION": 3,
        "VALID_SUBMISSION": 12
      },
      "C": {
        "MODEL_NONCOMPLETION": 5,
        "PROVIDER_CENSORED": 2,
        "VALID_SUBMISSION": 8
      },
      "D": {
        "MODEL_NONCOMPLETION": 5,
        "PROVIDER_CENSORED": 1,
        "VALID_SUBMISSION": 9
      }
    },
    "rows": [
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:16_08"
      },
      {
        "arm": "A",
        "category": "PROVIDER_CENSORED",
        "provider_error_at_deadline": true,
        "status": "PROVIDER_CENSORED",
        "task": "Template:16_08"
      },
      {
        "arm": "C",
        "category": "PROVIDER_CENSORED",
        "provider_error_at_deadline": true,
        "status": "PROVIDER_CENSORED",
        "task": "Template:16_08"
      },
      {
        "arm": "D",
        "category": "PROVIDER_CENSORED",
        "provider_error_at_deadline": true,
        "status": "MODEL_NONCOMPLETION",
        "task": "Template:16_08"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:09_02"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:09_02"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:09_02"
      },
      {
        "arm": "C",
        "category": "PROVIDER_CENSORED",
        "provider_error_at_deadline": true,
        "status": "MODEL_NONCOMPLETION",
        "task": "Financial_Model:09_02"
      },
      {
        "arm": "C",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:01_05"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:01_05"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:01_05"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:01_05"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Debugging:09_03"
      },
      {
        "arm": "A",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:09_03"
      },
      {
        "arm": "C",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:09_03"
      },
      {
        "arm": "D",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:09_03"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:18_05"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:18_05"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:18_05"
      },
      {
        "arm": "C",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:18_05"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:02_05"
      },
      {
        "arm": "C",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:02_05"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:02_05"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:02_05"
      },
      {
        "arm": "C",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:04_04"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:04_04"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:04_04"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:04_04"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:16_07"
      },
      {
        "arm": "C",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:16_07"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:16_07"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:16_07"
      },
      {
        "arm": "B",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Financial_Model:15_03"
      },
      {
        "arm": "C",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Financial_Model:15_03"
      },
      {
        "arm": "A",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Financial_Model:15_03"
      },
      {
        "arm": "D",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Financial_Model:15_03"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:06_02"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:06_02"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Template:06_02"
      },
      {
        "arm": "C",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Template:06_02"
      },
      {
        "arm": "C",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:02_04"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:02_04"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:02_04"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Financial_Model:02_04"
      },
      {
        "arm": "C",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Debugging:06_10"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Debugging:06_10"
      },
      {
        "arm": "D",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:06_10"
      },
      {
        "arm": "B",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:06_10"
      },
      {
        "arm": "A",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:04_07"
      },
      {
        "arm": "D",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Debugging:04_07"
      },
      {
        "arm": "C",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:04_07"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Debugging:04_07"
      },
      {
        "arm": "C",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Debugging:07_05"
      },
      {
        "arm": "B",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Debugging:07_05"
      },
      {
        "arm": "A",
        "category": "VALID_SUBMISSION",
        "provider_error_at_deadline": false,
        "status": "SUBMITTED",
        "task": "Debugging:07_05"
      },
      {
        "arm": "D",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:07_05"
      },
      {
        "arm": "B",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:01_04"
      },
      {
        "arm": "A",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:01_04"
      },
      {
        "arm": "D",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:01_04"
      },
      {
        "arm": "C",
        "category": "MODEL_NONCOMPLETION",
        "provider_error_at_deadline": false,
        "status": "MODEL_NONCOMPLETION",
        "task": "Debugging:01_04"
      }
    ]
  },
  "routing": {
    "note": "Default OpenRouter routing policy is common to arms; actually served provider may vary stochastically and is reported, not treated as a factorial arm.",
    "provider_wait_s_by_arm": {
      "A": 4879.05176768429,
      "B": 4048.0609026205457,
      "C": 5016.566482827002,
      "D": 6191.6057239495785
    },
    "served_models": {
      "z-ai/glm-5.3-flash": 1167
    },
    "served_providers_by_arm": {
      "A": {
        "DeepInfra": 1,
        "InferenceNet": 2,
        "Morph": 7,
        "OpenInference": 65,
        "Phala": 13,
        "Wafer": 241
      },
      "B": {
        "DeepInfra": 2,
        "InferenceNet": 9,
        "Morph": 1,
        "OpenInference": 52,
        "Phala": 14,
        "Wafer": 179
      },
      "C": {
        "InferenceNet": 13,
        "Morph": 1,
        "OpenInference": 64,
        "Phala": 26,
        "Wafer": 202
      },
      "D": {
        "DeepInfra": 1,
        "InferenceNet": 14,
        "Morph": 6,
        "OpenInference": 68,
        "Phala": 13,
        "Wafer": 173
      }
    }
  },
  "inspection": {
    "A": {
      "broad_views": 39,
      "formula_dump_calls": 126,
      "helper_mention_calls": 0,
      "helper_output_bytes_proxy": 0,
      "observation_bytes": 957611,
      "observation_local_tokens": 408245,
      "python_calls": 172,
      "python_stdout_bytes": 284513,
      "targeted_range_inspections": 44,
      "truncations": 42,
      "view_calls": 56,
      "whole_workbook_scans": 54
    },
    "B": {
      "broad_views": 30,
      "formula_dump_calls": 84,
      "helper_mention_calls": 4,
      "helper_output_bytes_proxy": 3599,
      "observation_bytes": 991270,
      "observation_local_tokens": 455702,
      "python_calls": 113,
      "python_stdout_bytes": 336560,
      "targeted_range_inspections": 25,
      "truncations": 44,
      "view_calls": 48,
      "whole_workbook_scans": 53
    },
    "C": {
      "broad_views": 24,
      "formula_dump_calls": 161,
      "helper_mention_calls": 0,
      "helper_output_bytes_proxy": 0,
      "observation_bytes": 1001872,
      "observation_local_tokens": 443575,
      "python_calls": 195,
      "python_stdout_bytes": 606846,
      "targeted_range_inspections": 26,
      "truncations": 39,
      "view_calls": 39,
      "whole_workbook_scans": 71
    },
    "D": {
      "broad_views": 12,
      "formula_dump_calls": 136,
      "helper_mention_calls": 0,
      "helper_output_bytes_proxy": 0,
      "observation_bytes": 1008265,
      "observation_local_tokens": 437116,
      "python_calls": 192,
      "python_stdout_bytes": 685468,
      "targeted_range_inspections": 25,
      "truncations": 47,
      "view_calls": 24,
      "whole_workbook_scans": 84
    }
  },
  "adoption": {
    "by_arm": {
      "A": {
        "helper_mention_calls": 0,
        "invocation_syntax_by_type": {},
        "runs_with_helper_mention": 0,
        "runs_with_invocation_syntax": 0
      },
      "B": {
        "helper_mention_calls": 4,
        "invocation_syntax_by_type": {
          "search": 6
        },
        "runs_with_helper_mention": 1,
        "runs_with_invocation_syntax": 1
      },
      "C": {
        "helper_mention_calls": 0,
        "invocation_syntax_by_type": {},
        "runs_with_helper_mention": 0,
        "runs_with_invocation_syntax": 0
      },
      "D": {
        "helper_mention_calls": 0,
        "invocation_syntax_by_type": {},
        "runs_with_helper_mention": 0,
        "runs_with_invocation_syntax": 0
      }
    },
    "limitation": "Command syntax plus return code requires transcript audit for actual execution and displacement; mention alone is not adoption."
  },
  "trajectory": {
    "A": {
      "assistant_output_tokens": 130269,
      "broad_view_share_of_views": 0.6964285714285714,
      "cumulative_prior_observation_bytes": 15308310,
      "fixed_schema_bytes": 296758,
      "helper_output_share_of_observation_bytes_proxy": 0.0,
      "input_tokens_per_call": 24189.951367781156,
      "max_prior_observation_bytes_on_call": 176688,
      "mean_calls_per_task": 21.933333333333334,
      "mean_prior_observation_bytes_per_call": 46529.81762917933,
      "python_inspection_share_of_calls": 0.5227963525835866,
      "tool_observation_bytes": 957611,
      "tool_observation_bytes_per_call": 2910.6717325227964,
      "tool_observation_local_tokens": 408245,
      "tool_observation_local_tokens_per_call": 1240.8662613981762,
      "total_input_tokens": 7958494,
      "total_model_calls": 329
    },
    "B": {
      "assistant_output_tokens": 108195,
      "broad_view_share_of_views": 0.625,
      "cumulative_prior_observation_bytes": 13078795,
      "fixed_schema_bytes": 231814,
      "helper_output_share_of_observation_bytes_proxy": 0.0036306959758693395,
      "input_tokens_per_call": 27676.143968871595,
      "max_prior_observation_bytes_on_call": 196884,
      "mean_calls_per_task": 17.133333333333333,
      "mean_prior_observation_bytes_per_call": 50890.25291828794,
      "python_inspection_share_of_calls": 0.4396887159533074,
      "tool_observation_bytes": 991270,
      "tool_observation_bytes_per_call": 3857.081712062257,
      "tool_observation_local_tokens": 455702,
      "tool_observation_local_tokens_per_call": 1773.1595330739299,
      "total_input_tokens": 7112769,
      "total_model_calls": 257
    },
    "C": {
      "assistant_output_tokens": 123974,
      "broad_view_share_of_views": 0.6153846153846154,
      "cumulative_prior_observation_bytes": 15454287,
      "fixed_schema_bytes": 276012,
      "helper_output_share_of_observation_bytes_proxy": 0.0,
      "input_tokens_per_call": 27256.398692810457,
      "max_prior_observation_bytes_on_call": 155807,
      "mean_calls_per_task": 20.4,
      "mean_prior_observation_bytes_per_call": 50504.205882352944,
      "python_inspection_share_of_calls": 0.6372549019607843,
      "tool_observation_bytes": 1001872,
      "tool_observation_bytes_per_call": 3274.091503267974,
      "tool_observation_local_tokens": 443575,
      "tool_observation_local_tokens_per_call": 1449.5915032679738,
      "total_input_tokens": 8340458,
      "total_model_calls": 306
    },
    "D": {
      "assistant_output_tokens": 165158,
      "broad_view_share_of_views": 0.5,
      "cumulative_prior_observation_bytes": 13845424,
      "fixed_schema_bytes": 248050,
      "helper_output_share_of_observation_bytes_proxy": 0.0,
      "input_tokens_per_call": 27407.84727272727,
      "max_prior_observation_bytes_on_call": 145123,
      "mean_calls_per_task": 18.333333333333332,
      "mean_prior_observation_bytes_per_call": 50346.99636363636,
      "python_inspection_share_of_calls": 0.6981818181818182,
      "tool_observation_bytes": 1008265,
      "tool_observation_bytes_per_call": 3666.418181818182,
      "tool_observation_local_tokens": 437116,
      "tool_observation_local_tokens_per_call": 1589.5127272727273,
      "total_input_tokens": 7537158,
      "total_model_calls": 275
    }
  },
  "token_to_success": {
    "A": {
      "score_floor_burden": "unavailable: no score floor was preregistered",
      "tokens_per_valid_submission": 795849.4,
      "total_input_tokens": 7958494,
      "uncensored_input_tokens": 7953682,
      "uncensored_tokens_per_valid_submission": 795368.2,
      "valid_submissions": 10
    },
    "B": {
      "score_floor_burden": "unavailable: no score floor was preregistered",
      "tokens_per_valid_submission": 592730.75,
      "total_input_tokens": 7112769,
      "uncensored_input_tokens": 7112769,
      "uncensored_tokens_per_valid_submission": 592730.75,
      "valid_submissions": 12
    },
    "C": {
      "score_floor_burden": "unavailable: no score floor was preregistered",
      "tokens_per_valid_submission": 1042557.25,
      "total_input_tokens": 8340458,
      "uncensored_input_tokens": 8141450,
      "uncensored_tokens_per_valid_submission": 1017681.25,
      "valid_submissions": 8
    },
    "D": {
      "score_floor_burden": "unavailable: no score floor was preregistered",
      "tokens_per_valid_submission": 837462.0,
      "total_input_tokens": 7537158,
      "uncensored_input_tokens": 7520466,
      "uncensored_tokens_per_valid_submission": 835607.3333333334,
      "valid_submissions": 9
    }
  },
  "replication_runs": []
}
```

Exact requests, responses, provider usage, local request decomposition, model-visible observations, official scores, and all primary and replication records are linked by the manifest in `token_claim_discovery/astra_packet_manifest.json`. Provider-reported token counts and local estimates are never substituted for one another.

Known limitations and contradictions include prior lower-token totals with completion/censoring confounding; treatment note overhead; helper adoption endogeneity; provider latency and served-model routing; model noncompletion; local tokenizer mismatch; and any task-level sign reversals shown above. The reserved validation tasks were not inspected for treatment outcomes.

## Frozen run order

| Task | Slot and arm sequence |
| --- | --- |
| Template:16_08 | 1:A, 2:B, 3:C, 4:D |
| Financial_Model:09_02 | 5:B, 6:C, 7:D, 8:A |
| Template:01_05 | 9:C, 10:D, 11:A, 12:B |
| Debugging:09_03 | 13:D, 14:A, 15:B, 16:C |
| Financial_Model:18_05 | 17:A, 18:B, 19:C, 20:D |
| Financial_Model:02_05 | 21:B, 22:C, 23:D, 24:A |
| Template:04_04 | 25:C, 26:D, 27:A, 28:B |
| Template:16_07 | 29:D, 30:A, 31:B, 32:C |
| Financial_Model:15_03 | 33:A, 34:B, 35:C, 36:D |
| Template:06_02 | 37:B, 38:C, 39:D, 40:A |
| Financial_Model:02_04 | 41:C, 42:D, 43:A, 44:B |
| Debugging:06_10 | 45:D, 46:A, 47:B, 48:C |
| Debugging:04_07 | 49:A, 50:B, 51:C, 52:D |
| Debugging:07_05 | 53:B, 54:C, 55:D, 56:A |
| Debugging:01_04 | 57:C, 58:D, 59:A, 60:B |

## Exact provider tool schemas and helper contract

```json
{
  "backend": "librecalc_agent 0.2.0rc1 reference openpyxl",
  "helper_on_signatures": [
    "search(workbook, pattern, regex=False, sheet=None)",
    "periods(workbook, sheet=None)",
    "inspect(workbook, sheet, cell_range, with_styles=False)"
  ],
  "provider_tool_schemas_all_arms": [
    {
      "function": {
        "description": "run shell commands (e.g., file operations, calling Python scripts with `python3`)",
        "name": "bash",
        "parameters": {
          "properties": {
            "command": {
              "description": "shell command to run",
              "type": "string"
            }
          },
          "required": [
            "command"
          ],
          "type": "object"
        }
      },
      "type": "function"
    },
    {
      "function": {
        "description": "view the content of an xlsx file. Can list all sheets or view a specific sheet's contents with optional row range",
        "name": "view_xlsx",
        "parameters": {
          "properties": {
            "end_row": {
              "type": "integer"
            },
            "file_path": {
              "type": "string"
            },
            "mode": {
              "description": "list or content",
              "type": "string"
            },
            "sheet": {
              "type": "string"
            },
            "start_row": {
              "type": "integer"
            }
          },
          "required": [
            "file_path"
          ],
          "type": "object"
        }
      },
      "type": "function"
    },
    {
      "function": {
        "description": "submits the current file",
        "name": "submit",
        "parameters": {
          "properties": {},
          "type": "object"
        }
      },
      "type": "function"
    }
  ],
  "provider_tool_schemas_differ": false,
  "reason": "Frozen RC helpers are Python-callable lx_helpers, not a new provider tool API. H factor is availability and its exact Python signatures in an addendum."
}
```

## Request decomposition and lineage

The 1167 final provider calls reconcile to the primary ledger. The raw append-only ledger retains 8 superseded successful calls from an interrupted partial block. `provider_usage_raw.jsonl` is frozen; `provider_usage.jsonl` is the derived selected-call view. Exact request segmentation is in `request_decomposition_exact.jsonl`, with provider counts separately in `provider_usage.jsonl`. Local cl100k estimates are not substituted for provider counts. All archived successful requests were decomposed: True.

| Arm | Calls | Prior observation bytes summed over calls | Mean prior-observation bytes/call | Reported cached input | Input minus cached | Provider-reported cost USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 329 | 15,308,310 | 46,529.818 | 7,169,913 | 788,581 | 0.281 |
| B | 257 | 13,078,795 | 50,890.253 | 6,330,225 | 782,544 | 0.256 |
| C | 306 | 15,454,287 | 50,504.206 | 7,596,337 | 744,121 | 0.289 |
| D | 275 | 13,845,424 | 50,346.996 | 6,681,127 | 856,031 | 0.295 |

## Mechanism and score contradictions

D/A after omitting two extreme Template tasks: `{'geometric_mean_ratio': 1.0956151184874532, 'median_ratio': 1.0341227007287925, 'n': 12, 'omitted': ['Template:01_05', 'Template:04_04']}`. Paired trajectory decomposition: `{'B_vs_A': {'completion_discordances': [{'control': 'MODEL_NONCOMPLETION', 'task': 'Debugging:04_07', 'treatment': 'SUBMITTED'}, {'control': 'MODEL_NONCOMPLETION', 'task': 'Debugging:09_03', 'treatment': 'SUBMITTED'}, {'control': 'SUBMITTED', 'task': 'Debugging:06_10', 'treatment': 'MODEL_NONCOMPLETION'}], 'geometric_call_count_ratio': 0.7537293647587097, 'geometric_input_tokens_per_call_ratio': 0.9367302859196753, 'geometric_total_input_ratio': 0.7060411233564814, 'n': 14}, 'C_vs_A': {'completion_discordances': [{'control': 'SUBMITTED', 'task': 'Template:06_02', 'treatment': 'MODEL_NONCOMPLETION'}], 'geometric_call_count_ratio': 0.910658961759334, 'geometric_input_tokens_per_call_ratio': 1.0161717943783686, 'geometric_total_input_ratio': 0.9253859512377245, 'n': 13}, 'D_vs_A': {'completion_discordances': [{'control': 'MODEL_NONCOMPLETION', 'task': 'Debugging:04_07', 'treatment': 'SUBMITTED'}, {'control': 'SUBMITTED', 'task': 'Debugging:07_05', 'treatment': 'MODEL_NONCOMPLETION'}, {'control': 'SUBMITTED', 'task': 'Debugging:06_10', 'treatment': 'MODEL_NONCOMPLETION'}], 'geometric_call_count_ratio': 0.8206713503328866, 'geometric_input_tokens_per_call_ratio': 1.040815984420509, 'geometric_total_input_ratio': 0.8541678593824318, 'n': 14}, 'D_vs_C': {'completion_discordances': [{'control': 'MODEL_NONCOMPLETION', 'task': 'Template:06_02', 'treatment': 'SUBMITTED'}, {'control': 'MODEL_NONCOMPLETION', 'task': 'Debugging:04_07', 'treatment': 'SUBMITTED'}, {'control': 'SUBMITTED', 'task': 'Debugging:07_05', 'treatment': 'MODEL_NONCOMPLETION'}, {'control': 'SUBMITTED', 'task': 'Debugging:06_10', 'treatment': 'MODEL_NONCOMPLETION'}], 'geometric_call_count_ratio': 0.8987532138276866, 'geometric_input_tokens_per_call_ratio': 1.017392449416653, 'geometric_total_input_ratio': 0.914384733637239, 'n': 13}}`.

Helper execution audit: `{'D_arm_helper_calls': 0, 'arm': 'B', 'audit_note': 'Transcript shows one type/iteration probe and one loop over result-object keys before the final command printed cell hits; return code 0 alone is not useful adoption.', 'command_calls': 4, 'command_rendering_cell_hits': 1, 'displacement_established': False, 'failed_command_calls': 1, 'model_visible_bytes_all_helper_commands': 3599, 'model_visible_bytes_successful_helper_commands': 2094, 'reason': 'One B run used the helper, but subsequent broad Python output and trajectory differences prevent mechanical attribution of the arm-level token contrast to displaced inspection.', 'runs_with_actual_helper_calls': 1, 'successful_command_calls': 3, 'task': 'Financial_Model:09_02', 'type': 'search'}`. One alias-imported helper user was missed by the first syntax detector, then corrected from frozen events. A/B/C/D broad views were 39, 30, 24, 12; model-visible observation bytes were 957611, 991270, 1001872, 1008265. Lower broad-view count did not yield lower observation burden.

D/A completion discordance: two A-only and one D-only valid submission. D/A low-token Template outputs include lower modification scores. B/A is favorable as a secondary contrast but has actual helper use in only one B task and none in D. C/A includes an extreme 22.7× Template trajectory in which the workbook was exact but no submit occurred. Provider routing and caching differ stochastically by arm despite a common policy. These are contradictions to any simple helper or salience token-saving story.

Replication decision: `{'eligible_conditions': ['one-arm provider censoring', 'D/A completion discordance', 'extreme >3x task ratios'], 'primary_results_unchanged': True, 'reason_not_run': 'The primary result is already frozen and fails the mechanism and robustness gates. Targeted repeats could diagnose pathologies but cannot rescue this preregistered discovery gate or turn this cohort into holdout validation.', 'replication_runs': 0}`. Historical normalization correction and interrupted partial-block recovery are preserved as distinct audit records. The future validation reservation remains untouched.

## My forensic read

I expect the earliest failure of the intended claim to be the proposed observation-burden mediator: per-call input and visible observation bytes did not fall. The combined median then depends on two Template trajectories and lacks a positive capability guard. A narrower note/availability effect is possible, particularly in B/A, but helper execution is too sparse to credit and the extra helper addendum is confounded with availability. This is a hypothesis for independent diagnosis, not a revised positive result.

## Questions for independent reviewer

1. Is the claimed token mechanism actually identified by this design?
2. Which contrast provides the strongest causal evidence?
3. Is any apparent token saving explained by completion, censoring, trajectory length, or call-count differences?
4. Does the salience note create a legitimate product effect or merely an experimental prompt artifact?
5. Do helper calls actually displace larger inspection work?
6. Is the D-vs-A effect decomposable into salience, helpers, and interaction?
7. Is the discovery gate too weak, too strong, or correctly scoped?
8. What is the earliest loss boundary if the claim fails?
9. What is the smallest product refinement justified by the evidence?
10. What should explicitly NOT be changed?
11. What fresh experiment would discriminate the leading explanations?
12. Is representative holdout validation justified?

## Affordance-induced verification / commitment hypothesis

Explicitly test whether B's lower call count is explained by a change in **verification and commitment behavior** rather than helper execution.

The hypothesis is:

> Merely knowing that narrow factual lookup capability is available may change the model's policy: it may commit to an interpretation/edit sooner, perform fewer redundant inspections or double-checks, or avoid reopening/re-reading facts it considers mechanically recoverable if needed — even when it never actually invokes the helper.

Do NOT assume this is true.

Using the frozen trajectories, classify model/tool activity where mechanically defensible into:

```text
initial discovery / navigation

new-evidence inspection

hypothesis testing

reinspection of previously observed facts

verification / double-checking before edit

post-edit verification

reopen / reread after mutation

repeated formula-chain or range inspection

additional inspection after the required edit is already mechanically complete

other / ambiguous
```

Compare A versus B first, with C/D only as supporting contrasts.

Answer specifically:

1. Does B perform fewer verification/reinspection cycles than A?

2. Does B reach its first mutation materially earlier in model-call count?

3. Does B submit materially sooner after its final mutation?

4. Are there fewer workbook reopens or rereads after relevant facts have already been observed?

5. Are repeated reads of the same cells/ranges/facts lower in B?

6. Are fewer model calls explained by less redundant checking, or simply by unrelated trajectory divergence?

7. Is there evidence that B commits to a correct-enough solution earlier without reducing workbook quality?

8. Does the one actual helper-using B run behave differently from the B runs that merely knew helpers were available?

9. Among B runs with zero helper invocation, is there still a systematic verification/commitment difference relative to A?

10. Is the best description of any supported effect:

```text
HELPER EXECUTION

HELPER AVAILABILITY / AFFORDANCE

TEXTUAL PRIMING

EARLIER COMMITMENT

REDUCED REDUNDANT VERIFICATION

GENERAL TRAJECTORY VARIANCE

NOT IDENTIFIABLE
```

Do not infer model confidence or internal mental state.

Use observable behavior only.

If an affordance-induced reduction in redundant verification is supported, explain the smallest fresh experiment that would distinguish:

```text
mere textual cue that "a helper exists"

actual helper availability

credible ability to query the helper if needed

generic statement that precise factual lookup is available

no affordance cue
```

The goal is to determine whether the product changes **how much checking the agent believes it needs to perform**, while describing that entirely through observable trajectory behavior rather than anthropomorphic claims.