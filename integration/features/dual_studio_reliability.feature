# language: es
Característica: Entrega reproducible de ambos estudios sin credenciales externas
  Las pruebas offline verifican contratos del producto y no certifican generación con IA real.

  Esquema del escenario: El texto inicial sobrevive a la apertura y recarga de Requisitos
    Dado un estudio "<estudio>" aislado
    Y una sesión nueva con requisitos contables
    Cuando recupero los requisitos dos veces
    Entonces conservo el texto original sin inventar una revisión
    Ejemplos:
      | estudio    |
      | springboot |
      | quarkus    |

  Esquema del escenario: Una revisión obsoleta no puede reemplazar la revisión vigente
    Dado un estudio "<estudio>" aislado
    Y una sesión nueva con requisitos contables
    Y una revisión contable aprobada
    Cuando guardo un cambio y vuelvo a guardar desde la revisión anterior
    Entonces recibo conflicto y conservo el cambio vigente
    Ejemplos:
      | estudio    |
      | springboot |
      | quarkus    |

  Esquema del escenario: Entregar fuentes conserva el dominio y declara la verificación omitida
    Dado un estudio "<estudio>" aislado
    Y una sesión nueva con requisitos contables
    Y una revisión contable aprobada
    Cuando ejecuto la entrada "<entrada>" usando el proveedor diagnóstico explícito
    Entonces la sesión termina con verificación omitida por elección
    Y la revisión y el dominio contable permanecen completos
    Y puedo descargar un ZIP de las fuentes
    Ejemplos:
      | estudio    | entrada   |
      | springboot | manual    |
      | springboot | guiado    |
      | springboot | autopilot |
      | quarkus    | manual    |
      | quarkus    | guiado    |
      | quarkus    | autopilot |
