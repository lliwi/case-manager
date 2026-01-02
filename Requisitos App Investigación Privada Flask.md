# **Requisitos Técnicos y Funcionales para un Ecosistema Digital de Investigación Privada: Arquitectura Forense en Flask y Docker bajo el Marco de la Ley 5/2014**

La digitalización de la investigación privada en España no representa únicamente una transición tecnológica, sino una adaptación necesaria a un entorno donde la prueba digital y la trazabilidad de las actuaciones son fundamentales para el éxito judicial. El desarrollo de una plataforma orientada a detectives privados debe integrar la rigurosidad procesal impuesta por la Ley 5/2014 de Seguridad Privada con la flexibilidad técnica que permiten herramientas modernas como Flask y la orquestación de contenedores mediante Docker. En este sentido, la arquitectura no solo debe facilitar el almacenamiento de información, sino garantizar la integridad forense, la capacidad de análisis relacional a través de grafos y la visualización cronológica de los eventos investigativos, todo ello manteniendo un sistema modular de extensiones para herramientas OSINT y forenses.

## **El Marco Legal Español como Pilar Funcional: La Ley 5/2014**

La piedra angular de cualquier sistema destinado a la investigación privada en territorio español es el cumplimiento estricto de la Ley 5/2014, de 4 de abril, de Seguridad Privada. Esta normativa establece que el detective privado es el único profesional habilitado para realizar averiguaciones sobre conductas o hechos privados con el fin de obtener y aportar información y pruebas ante terceros legitimados.1 Un requisito funcional primario e ineludible es la gestión del Libro-registro de operaciones, el cual debe estar integrado de forma nativa en la aplicación para cumplir con el artículo 25 de la citada ley.3 La automatización de este registro asegura que cada encargo de investigación sea documentado cronológicamente, incluyendo datos críticos como el número de orden, la fecha de inicio, la identificación del cliente y de los sujetos investigados, así como el objeto de la investigación.3

La aplicación debe implementar un flujo de trabajo que valide la legitimación del encargo antes de permitir la carga de cualquier tipo de evidencia. El interés legítimo es una condición previa para la validez de la investigación; por ejemplo, en casos de control de bajas laborales, la empresa posee un interés legítimo para verificar si el empleado está realizando actividades incompatibles con su estado de incapacidad.5 La plataforma debe obligar al investigador a cargar el contrato de servicios o el documento que acredite dicha legitimación como paso previo a la apertura de un expediente digital.7 Asimismo, el sistema debe contemplar la prohibición taxativa de investigar delitos perseguibles de oficio; en caso de que el sistema detecte, mediante análisis de palabras clave o etiquetas, hechos que pudieran ser constitutivos de tales delitos, debe activar un protocolo de bloqueo y notificación para que el detective cumpla con su deber de denuncia inmediata ante las autoridades competentes.2

| Concepto Legal (Ley 5/2014) | Requisito Funcional del Sistema | Implicación Técnica |
| :---- | :---- | :---- |
| Deber de Registro (Art. 25\) | Generación automática de Libro-registro inmutable.3 | Base de datos con logs de auditoría y sellado de tiempo. |
| Interés Legítimo | Formulario de validación de causa de investigación.6 | Campo obligatorio de adjunto documental para apertura de caso. |
| Identificación Profesional | Gestión de perfiles con número de TIP del detective.10 | Autenticación vinculada a número de registro profesional. |
| Deber de Reserva | Encriptación de datos en reposo y tránsito. | Implementación de TLS y cifrado AES-256 en volúmenes Docker. |
| Ratificación de Informes | Exportación de informes técnicos para sede judicial.11 | Generador de PDF con metadatos de integridad y firmas digitales. |

## **Arquitectura de Microservicios: Flask y Docker en Entornos de Investigación**

La elección de una arquitectura basada en Flask responde a la necesidad de un núcleo ligero y altamente extensible. Flask permite la implementación del patrón de fábrica de aplicaciones (Application Factory), lo que facilita la carga dinámica de configuraciones y la segregación de funciones mediante Blueprints.13 Por otro lado, la contenedorización mediante Docker resulta indispensable para asegurar la reproducibilidad del entorno y el aislamiento de los procesos. En una investigación forense, la consistencia de las herramientas utilizadas es vital para evitar cuestionamientos sobre la manipulación de la evidencia.14

La orquestación se estructura a través de un ecosistema de contenedores interconectados, donde cada servicio cumple una función específica dentro del ciclo de vida de la investigación. Se propone una estructura de servicios que separe la lógica de presentación, el procesamiento intensivo y el almacenamiento persistente.

### **Desglose de Servicios en Docker-Compose**

Para garantizar la escalabilidad y la robustez, el sistema debe desplegarse mediante múltiples contenedores que se comunican a través de una red interna aislada.

1. **Contenedor Web (Flask):** Encargado de gestionar la interfaz de usuario y la API REST. Debe configurarse para no ejecutarse como usuario root para mitigar vulnerabilidades de seguridad.  
2. **Base de Datos Relacional (PostgreSQL):** Almacenará la información estructurada que requiere integridad transaccional absoluta, como los expedientes del Libro-registro y los perfiles de usuario.3  
3. **Base de Datos de Grafos (Neo4j):** Gestionará las relaciones entre entidades (personas, vehículos, ubicaciones). La elección de Neo4j se justifica por su capacidad nativa para realizar travesías de relaciones complejas sin la penalización de rendimiento que suponen los JOINs en SQL.17  
4. **Broker de Mensajes (Redis):** Actuará como intermediario para la gestión de tareas asíncronas.20  
5. **Trabajadores de Celery (Workers):** Ejecutarán los plugins de procesamiento pesado, como la extracción de metadatos EXIF de grandes volúmenes de imágenes o la ejecución de scripts OSINT de larga duración.13  
6. **Servidor de Monitorización (Flower):** Permitirá al administrador supervisar el estado de las tareas asíncronas en tiempo real.20

El uso de volúmenes persistentes en Docker es crítico. La información almacenada en /data (evidencias) y en los volúmenes de las bases de datos debe estar vinculada a particiones físicas del host que cuenten con cifrado de disco completo. Esto asegura que, en caso de incautación física del servidor, los datos de las investigaciones no sean accesibles sin las claves criptográficas adecuadas, cumpliendo con el deber de reserva profesional.7

## **Gestión de Casos y Evidencias: Integridad Forense y Cadena de Custodia**

La gestión de evidencias dentro de la plataforma debe seguir rigurosamente las fases del análisis forense digital establecidas en la norma UNE 71506: preservación, adquisición, documentación, análisis y presentación.14 Cada archivo incorporado a un caso debe ser tratado como un objeto inmutable. En el momento de la carga, el sistema debe calcular inmediatamente múltiples hashes de integridad (como SHA-256 y SHA-512) y registrar este valor junto con la fecha y hora proporcionada por un servidor de sellado de tiempo confiable.22 Este procedimiento es el único que garantiza la "mismidad" de la prueba, asegurando al tribunal que la evidencia presentada no ha sufrido alteraciones desde su recolección.24

La cadena de custodia digital debe documentar cronológicamente cada interacción con la evidencia. La aplicación ha de registrar quién accedió a qué archivo, en qué momento y desde qué dirección IP.15 Estos registros de auditoría no deben ser editables ni eliminables por ningún usuario, ni siquiera por el administrador, para mantener la transparencia exigida en procesos judiciales.23

### **Metodología de Adquisición y Documentación de Evidencias**

El sistema debe facilitar la documentación de la fase de adquisición. Si se trata de evidencias obtenidas de dispositivos físicos, la plataforma permitirá adjuntar actas de recolección que detallen el estado del dispositivo (encendido o apagado), las herramientas de clonado empleadas y las incidencias detectadas en el lugar del incidente.14 Para las evidencias digitales nativas de la aplicación (como capturas de pantalla de redes sociales), el sistema debe integrar metadatos técnicos de captura de forma automática.

| Fase Forense (UNE 71506\) | Acción Técnica en la Plataforma | Resultado Esperado |
| :---- | :---- | :---- |
| Preservación | Almacenamiento en volúmenes cifrados y generación de hash inicial.14 | Evidencia aislada de alteraciones externas. |
| Adquisición | Registro de clonado a bajo nivel y estado de sistemas.14 | Trazabilidad del origen del dato. |
| Documentación | Generación de log de auditoría inmutable (Audit Trail).23 | Cadena de custodia verificable. |
| Análisis | Ejecución de plugins de extracción y recuperación de datos.14 | Obtención de información relevante oculta. |
| Presentación | Exportación de informes en lenguaje inteligible con anexos de hash.1 | Prueba admisible y comprensible judicialmente. |

## **El Grafo de Relaciones: Motor de Inteligencia y Conexión de Datos**

Una de las funcionalidades más innovadoras requeridas es el grafo de relaciones. En la investigación privada, los datos rara vez existen de forma aislada. Una dirección IP puede estar vinculada a un correo electrónico, que a su vez está asociado a un perfil de redes sociales, el cual contiene fotografías de un vehículo cuya matrícula ha sido vista en una ubicación específica.18 El uso de Neo4j como motor de persistencia para estas relaciones permite al detective realizar descubrimientos que serían prácticamente imposibles en un modelo relacional tradicional.

### **Implementación del Modelo de Grafo de Propiedades**

El sistema modelará la investigación como un grafo de propiedades donde los nodos representan entidades y las aristas representan los vínculos entre ellas.

* **Nodos de Entidad:** Personas, Empresas, Teléfonos, Correos Electrónicos, Perfiles Sociales, Vehículos, Direcciones Físicas, Cuentas Bancarias (bajo orden judicial si aplica), y Evidencias Digitales.  
* **Relaciones:** "FAMILIAR\_DE", "SOCIO\_DE", "UTILIZA\_VEHÍCULO", "VISTO\_EN", "VINCULADO\_A\_EVIDENCIA", "PUBLICADO\_DESDE".

La ventaja competitiva de este modelo radica en la capacidad de realizar consultas de travesía (traversal) para encontrar vínculos indirectos. Por ejemplo, mediante una consulta en lenguaje Cypher, se puede identificar si dos sujetos investigados en casos distintos han compartido un mismo punto de acceso Wi-Fi o si frecuentan el mismo domicilio en horarios coincidentes.29 Esta estructura de datos se integra directamente con la línea de tiempo, permitiendo visualizar cómo evolucionan estas relaciones a lo largo de los meses de seguimiento.19

| Característica | Base de Datos Relacional (SQL) | Base de Datos de Grafos (Neo4j) |
| :---- | :---- | :---- |
| Estructura | Tablas fijas y filas. | Nodos, relaciones y propiedades. |
| Relaciones | Definidas mediante claves foráneas y JOINs. | Elementos de primer nivel (nativas).18 |
| Rendimiento en Consultas Complejas | Degradación exponencial con el número de JOINs.18 | Rendimiento constante independientemente de la profundidad. |
| Flexibilidad de Esquema | Rígido; requiere migraciones costosas. | Esquema flexible; permite añadir tipos de relaciones dinámicamente. |
| Casos de Uso | Gestión administrativa, Libro-registro. | Análisis de redes sociales, detección de fraude laboral.32 |

## **Línea de Tiempo Investigativa: Visualización del Comportamiento Temporal**

La línea de tiempo es el componente visual que permite sintetizar los hallazgos de la investigación para su presentación judicial. Especialmente en casos de bajas laborales fraudulentas, la capacidad de mostrar cronológicamente las actividades del investigado es determinante.8 El sistema debe integrar eventos procedentes de diversas fuentes: notas de vigilancia física, registros de geolocalización (siempre que se obtengan de forma legal y proporcionada), publicaciones en redes sociales extraídas por plugins OSINT y eventos técnicos de evidencias digitales.35

Mediante el uso de bibliotecas como Vis.js o Plotly, la interfaz de usuario debe permitir una navegación fluida, con capacidad de zoom y filtrado por categorías. Un evento en la línea de tiempo debe funcionar como un hipervínculo que lleve directamente a la evidencia que lo sustenta, permitiendo que el informe digital sea interactivo antes de su exportación final.36

### **Funcionalidades de la Línea de Tiempo Investigativa**

La implementación técnica de la línea de tiempo debe contemplar:

* **Agrupamiento por Sujeto:** Visualización de múltiples líneas temporales paralelas para comparar la actividad de diferentes investigados o sospechosos.36  
* **Identificación de Patrones:** Capacidad para resaltar recurrencias horarias o geográficas que sugieran rutinas de trabajo o de ocio incompatibles con una lesión alegada.8  
* **Sincronización de Multimedia:** Reproducción de fragmentos de vídeo o visualización de fotos directamente desde el punto cronológico correspondiente.36  
* **Marcadores de Hitos:** Señalización de momentos clave de la investigación, como la fecha de inicio de la supuesta baja médica o el día de una reunión relevante.

## **Sistema de Plugins: Modularidad y Extensibilidad del Ecosistema**

La naturaleza cambiante de la tecnología forense y OSINT exige que la aplicación no sea un monolito cerrado, sino una plataforma que admita extensiones. El sistema de plugins debe permitir a los desarrolladores y peritos añadir nuevas capacidades sin alterar el núcleo de Flask. Se recomienda el uso de pluggy, el sistema de hooks que utiliza pytest, o stevedore, que permite gestionar plugins basados en puntos de entrada (entry points) de Python.38

### **Arquitectura del Sistema de Extensiones**

Los plugins se cargarán dinámicamente al inicio de la aplicación, registrándose en categorías específicas según su funcionalidad.

1. **Plugins de Extracción de Metadatos:** Utilizarán bibliotecas como Pillow para imágenes, Mutagen para audio/vídeo y PyPDF2 para documentos, permitiendo extraer información técnica y metadatos XMP de forma masiva.27  
2. **Plugins de Verificación de Identidad:** Implementación de validadores para DNI/NIE españoles basándose en algoritmos de dígito de control. El cálculo consiste en obtener el resto de dividir el número del DNI entre 23 y mapear ese valor a una tabla de letras estandarizada por el Ministerio del Interior.43  
3. **Plugins de OSINT y Enriquecimiento:** Consultas automáticas a servicios de búsqueda inversa de correos electrónicos o teléfonos, como Holehe (para verificar registros en más de 120 sitios web mediante la función de recuperación de contraseña) o Sherlock (para búsqueda de nombres de usuario).46  
4. **Plugins de Verificación de Correo (Email Verification):** Comprobación de existencia de cuentas y registros MX, así como presencia en bases de datos de brechas de seguridad para establecer antecedentes del sujeto.28

| Categoría de Plugin | Herramienta / Biblioteca Recomendada | Funcionalidad Específica |
| :---- | :---- | :---- |
| Forense (Imagen) | Pillow / ExifTool 41 | Extracción de GPS, modelo de cámara y fecha original. |
| Forense (Documento) | PyPDF2 / OleFileIO\_PL 42 | Análisis de autoría, historial de edición y metadatos XMP. |
| OSINT (Identidad) | python-stdnum / spanish-dni 43 | Validación de integridad de DNI/NIE/CIF españoles. |
| OSINT (Social) | Holehe / Sherlock 46 | Detección de perfiles vinculados a correos o alias. |
| Multimedia | Mutagen 42 | Extracción de metadatos en archivos MP3/MP4 para investigación de audio. |

## **Monitorización de Eventos y Sujetos: Inteligencia Proactiva**

La aplicación debe ir más allá de la recopilación estática de datos y permitir la monitorización activa. Este requisito funcional se divide en dos vertientes: la monitorización de flujos de datos digitales y el seguimiento de la actividad de personas físicas dentro de los marcos legales establecidos.

### **Monitorización Digital de Fuentes Abiertas**

Utilizando tareas programadas de Celery, el sistema puede monitorizar cambios en perfiles públicos de redes sociales, la aparición de nuevas menciones de una marca o persona en motores de búsqueda, o la alteración de registros en dominios específicos.28 La plataforma permitirá configurar alertas basadas en palabras clave o cambios en la estructura de un sitio web. Cuando se detecte una coincidencia, el sistema generará automáticamente un evento en la línea de tiempo y notificará al detective, capturando la evidencia digital de forma inmediata para evitar su pérdida por borrado accidental o intencionado por parte del sujeto investigado.28

### **Monitorización de Sujetos y Ética Legal**

En la investigación física, la monitorización se apoya en diarios de vigilancia. Sin embargo, la integración tecnológica de dispositivos como localizadores GPS debe manejarse con extrema precaución técnica y legal. Según la jurisprudencia española actual (STS 278/2021), el uso de dispositivos GPS en vehículos de personas que no son parte de un procedimiento judicial, o sin el consentimiento del titular del vehículo, puede constituir una vulneración del derecho fundamental a la intimidad personal.53 Por este motivo, los requisitos técnicos de la aplicación deben priorizar el registro manual o semiautomático de ubicaciones basadas en la observación directa del detective, evitando la automatización de rastreos GPS intrusivos que puedan invalidar toda la investigación.53

La aplicación debe incluir un módulo de "Razonabilidad y Proporcionalidad" que obligue al detective a justificar por qué una medida de seguimiento específica es necesaria e idónea para el caso concreto, creando una defensa sólida para la posterior ratificación judicial del informe.10

## **Buenas Prácticas en Informática Forense y OSINT**

La arquitectura técnica debe encarnar las buenas prácticas internacionales para que los resultados sean admisibles ante tribunales de cualquier jurisdicción, especialmente la española. Esto implica no solo el uso de herramientas de código abierto probadas, sino también la implementación de flujos de trabajo científicos.

### **El Proceso de Análisis y Recuperación de Datos**

Dentro de los requisitos funcionales de los plugins forenses, se debe incluir la capacidad de analizar particiones y sistemas de archivos para recuperar datos borrados que puedan ser cruciales en investigaciones de fraude o competencia desleal.14 Herramientas como Sleuth Kit pueden integrarse mediante envoltorios (wrappers) en Python para permitir al detective realizar un examen minucioso de las estructuras de datos sin salir de la plataforma.60 El análisis debe ser no destructivo, trabajando siempre sobre copias bit a bit de las evidencias originales.14

### **OSINT: De la Recolección al Análisis Relacional**

El sistema debe facilitar la transformación de datos no estructurados de la web en nodos y relaciones del grafo. Por ejemplo, al ejecutar un plugin de búsqueda de correo electrónico, los resultados (redes sociales vinculadas, brechas de datos, perfiles en foros) no deben presentarse como un simple texto, sino como entidades sugeridas que el detective puede "vincular" al grafo principal del caso.28 La integración de Maltego o herramientas similares de visualización de enlaces (Link Analysis) proporciona un modelo a seguir para la interfaz del grafo en la aplicación.28

### **Validación de Identidad Digital: El Algoritmo del DNI**

Para la verificación de documentos de identidad, el sistema debe implementar una validación algorítmica estricta. Un plugin especializado debe procesar el número de identificación fiscal (NIF/NIE) asegurando que el formato y el dígito de control sean correctos antes de darlos por válidos en el Libro-registro.

La fórmula para la validación del NIF español es la siguiente:  
Dado un número de 8 dígitos $N$, el índice de la letra de control $I$ se calcula como:

$$I \= N \\pmod{23}$$

Este índice $I$ se corresponde con una posición en la cadena de caracteres estandarizada "TRWAGMYFPDXBNJZSQVHLCKE".44 La aplicación debe realizar este cálculo en tiempo real durante la entrada de datos, notificando cualquier inconsistencia que pudiera sugerir una identidad falsa o un error tipográfico.43

## **Seguridad de la Plataforma y Protección de la Información**

La exclusión explícita de la LOPDGDD de los requisitos no exime al sistema de la necesidad de una seguridad técnica de alto nivel. El deber de reserva y secreto profesional del detective privado (Art. 50 de la Ley 5/2014) exige que el sistema sea inexpugnable ante terceros.

### **Endurecimiento de Contenedores y Redes**

La configuración de Docker debe implementar estrategias de defensa en profundidad:

* **Aislamiento de Servicios:** Los servicios de bases de datos no deben tener puertos mapeados al host, siendo accesibles únicamente por la aplicación Flask a través de una red interna cifrada.  
* **Escaneo de Vulnerabilidades:** Los contenedores deben basarse en imágenes mínimas (como Alpine o Debian Slim) y ser escaneados regularmente en busca de CVEs conocidos.  
* **Gestión de Identidades y Accesos (IAM):** Implementación de autenticación multifactor (MFA) para los detectives, vinculando el acceso a certificados digitales o tokens de hardware. Dado que el detective debe ser el único que gestiona sus expedientes, el sistema debe emplear un modelo de "Zero Knowledge" siempre que sea posible para el almacenamiento de las evidencias más sensibles.

### **Integridad de Datos y Logs de Auditoría**

El sistema de logs debe ser centralizado y protegido contra escritura. Cada acción realizada en la plataforma, desde la apertura de un caso hasta la visualización de una fotografía, debe quedar registrada de forma que sea auditable judicialmente. Este "Audit Trail" es la garantía final de que la evidencia no ha sido contaminada por el propio investigador o por un actor externo malintencionado.23

## **Elaboración del Informe de Investigación y Ratificación Judicial**

El resultado final de toda la actividad técnica y funcional de la aplicación es la generación del informe de investigación. Este documento no es una simple recopilación de hechos, sino un medio de prueba personal (no documental) que debe ser defendido por el detective ante el juez.11 La aplicación debe automatizar la consolidación de los hallazgos en un documento coherente, estructurado y legalmente válido.

### **Estructura Automatizada del Informe Final**

El motor de generación de informes de la aplicación deberá seguir los estándares de la Ley 5/2014 y las recomendaciones de las asociaciones profesionales de detectives:

1. **Identificación del Investigador:** Nombre, TIP y despacho.10  
2. **Identificación del Cliente y Legitimación:** Explicación del interés legítimo que motivó la investigación.6  
3. **Objeto de la Investigación:** Descripción clara de los hechos que se pretendían esclarecer.  
4. **Metodología y Herramientas:** Detalle técnico de los medios utilizados, incluyendo los hashes de los archivos multimedia y las herramientas OSINT o forenses empleadas.1  
5. **Relación de Hechos (Cuerpo del Informe):** Narrativa cronológica apoyada por la línea de tiempo y el grafo de relaciones, con referencias cruzadas a las evidencias del anexo.  
6. **Anexos Técnicos:** Listado detallado de todas las evidencias digitales con sus correspondientes sellos de tiempo y firmas digitales para garantizar la trazabilidad completa.

La aplicación debe asegurar que el lenguaje utilizado en el informe sea inteligible. Aunque la investigación sea técnicamente compleja (por ejemplo, el rastreo de una criptomoneda o el análisis de metadatos de un archivo OLE de Office), el informe debe traducir esos hallazgos en términos que un magistrado pueda interpretar sin necesidad de conocimientos técnicos avanzados, cumpliendo así con el objetivo final del peritaje informático.1

## **Conclusiones**

El desarrollo de una plataforma de investigación privada bajo Flask y Docker representa la convergencia necesaria entre la técnica forense moderna y la normativa legal española. La integración de un grafo de relaciones y una línea de tiempo interactiva no solo mejora la capacidad analítica del detective, sino que eleva la calidad de la prueba presentada ante la justicia. Al basar el diseño en la Ley 5/2014 y en normativas técnicas como la UNE 71506, se garantiza que cada paso de la investigación —desde la validación inicial del interés legítimo hasta la generación del informe final— sea rastreable, íntegro y jurídicamente robusto.

La modularidad que ofrece el sistema de plugins permite que esta herramienta evolucione al ritmo de las nuevas amenazas y tecnologías, asegurando que el detective privado cuente siempre con las mejores capacidades de extracción de metadatos, verificación de identidad y monitorización de objetivos. En última instancia, la digitalización de la investigación privada no consiste solo en usar computadoras, sino en construir ecosistemas de confianza donde la integridad del dato y la rigurosidad del proceso sean los pilares de la verdad judicial. La arquitectura aquí propuesta sienta las bases para un entorno de trabajo seguro, eficiente y plenamente alineado con las exigencias del siglo XXI.

#### **Works cited**

1. La validez jurídica del informe de investigación privada, accessed on January 1, 2026, [https://www.investiberica.com/la-validez-juridica-del-informe-de-investigacion-privada/](https://www.investiberica.com/la-validez-juridica-del-informe-de-investigacion-privada/)  
2. Contratar detective privado | Marco legal | Privalia, accessed on January 1, 2026, [https://www.privaliadetectives.com/contratar-detective-privado/](https://www.privaliadetectives.com/contratar-detective-privado/)  
3. Libro-registro \- Detectives Privados \- Ministerio del Interior, accessed on January 1, 2026, [https://www.interior.gob.es/opencms/en/servicios-al-ciudadano/tramites-y-gestiones/personal-de-seguridad-privada/detectives-privados/libro-registro/](https://www.interior.gob.es/opencms/en/servicios-al-ciudadano/tramites-y-gestiones/personal-de-seguridad-privada/detectives-privados/libro-registro/)  
4. Nuevo Reglamento Seguridad Privada \- ASM Formación, accessed on January 1, 2026, [https://www.asm-formacion.es/oposicion/oferta\_formativa/presencial/Contenido\_presencial/Nuevo%20Reglamento%20Seguridad%20Privada.pdf](https://www.asm-formacion.es/oposicion/oferta_formativa/presencial/Contenido_presencial/Nuevo%20Reglamento%20Seguridad%20Privada.pdf)  
5. Detectives privados y la lucha contra el fraude en bajas laborales, accessed on January 1, 2026, [https://mascalvet.com/en/detectives-privados-y-la-lucha-contra-el-fraude-en-bajas-laborales-un-aliado-para-empresas-y-mutuas/](https://mascalvet.com/en/detectives-privados-y-la-lucha-contra-el-fraude-en-bajas-laborales-un-aliado-para-empresas-y-mutuas/)  
6. Control de trabajadores de baja médica: ¿Cuándo puede la ..., accessed on January 1, 2026, [https://asesoriatauste.es/control-de-trabajadores-de-baja-medica-cuando-puede-la-empresa-contratar-a-un-detective/](https://asesoriatauste.es/control-de-trabajadores-de-baja-medica-cuando-puede-la-empresa-contratar-a-un-detective/)  
7. Despachos de Detectives \- Ministerio del Interior, accessed on January 1, 2026, [https://www.interior.gob.es/opencms/es/servicios-al-ciudadano/tramites-y-gestiones/personal-de-seguridad-privada/detectives-privados/despachos-de-detectives/](https://www.interior.gob.es/opencms/es/servicios-al-ciudadano/tramites-y-gestiones/personal-de-seguridad-privada/detectives-privados/despachos-de-detectives/)  
8. Detectives para bajas laborales, accessed on January 1, 2026, [https://detectivesteson.com/detectives-para-bajas-laborlaes/](https://detectivesteson.com/detectives-para-bajas-laborlaes/)  
9. Ley de Seguridad Privada \- Detectives Morellá, accessed on January 1, 2026, [https://www.detectivesmorella.net/noticias-detectives-privados/noticia.php?noticia=46](https://www.detectivesmorella.net/noticias-detectives-privados/noticia.php?noticia=46)  
10. El informe del detective privado, accessed on January 1, 2026, [https://agenciagranvia.com/marco-legal/](https://agenciagranvia.com/marco-legal/)  
11. Regulación y límites de la Investigación Privada en la Ley 5/2014 ..., accessed on January 1, 2026, [https://cronicaseguridad.com/2024/07/11/regulacion-y-limites-de-la-investigacion-privada-en-la-ley-5-2014-de-seguridad-privada-parte-ii/](https://cronicaseguridad.com/2024/07/11/regulacion-y-limites-de-la-investigacion-privada-en-la-ley-5-2014-de-seguridad-privada-parte-ii/)  
12. La investigación penal del detective y su valor probatorio (Resumen), accessed on January 1, 2026, [https://portalinvestigacion.uniovi.es/documentos/6463c21531071d0076f824d8](https://portalinvestigacion.uniovi.es/documentos/6463c21531071d0076f824d8)  
13. Patterns for Flask — Flask Documentation (3.1.x), accessed on January 1, 2026, [https://flask.palletsprojects.com/en/stable/patterns/](https://flask.palletsprojects.com/en/stable/patterns/)  
14. ISO 71506/2013. Metodología para el análisis forense de las ..., accessed on January 1, 2026, [https://peritosinformaticos.es/iso-71506-2013-perito-informatico/](https://peritosinformaticos.es/iso-71506-2013-perito-informatico/)  
15. Digital Evidence Chain of Custody \- SEFCOM, accessed on January 1, 2026, [https://sefcom.asu.edu/publications/CoC-SoK-tps2024.pdf](https://sefcom.asu.edu/publications/CoC-SoK-tps2024.pdf)  
16. BOE-A-2014-3649 Ley 5/2014, de 4 de abril, de Seguridad Privada., accessed on January 1, 2026, [https://www.boe.es/buscar/act.php?id=BOE-A-2014-3649](https://www.boe.es/buscar/act.php?id=BOE-A-2014-3649)  
17. A Comparison between a Relational and a Graph Database in the ..., accessed on January 1, 2026, [https://annals-csis.org/Volume\_26/drp/pdf/33.pdf](https://annals-csis.org/Volume_26/drp/pdf/33.pdf)  
18. Graph Database vs. Relational Database: What's The Difference?, accessed on January 1, 2026, [https://neo4j.com/blog/graph-database/graph-database-vs-relational-database/](https://neo4j.com/blog/graph-database/graph-database-vs-relational-database/)  
19. Top 10 Graph Database Use Cases (With Real-World Case Studies), accessed on January 1, 2026, [https://neo4j.com/blog/graph-database/graph-database-use-cases/](https://neo4j.com/blog/graph-database/graph-database-use-cases/)  
20. mattkohl/docker-flask-celery-redis \- GitHub, accessed on January 1, 2026, [https://github.com/mattkohl/docker-flask-celery-redis](https://github.com/mattkohl/docker-flask-celery-redis)  
21. flask-celery-docker \- Sean Carroll \- GitLab, accessed on January 1, 2026, [https://gitlab.com/sfcarroll/flask-celery-docker](https://gitlab.com/sfcarroll/flask-celery-docker)  
22. International Journal of Multidisciplinary \- ijmrset, accessed on January 1, 2026, [https://www.ijmrset.com/upload/46\_Blockchain%20and%20Deep%20Learning%20for%20Ensuring%20Integrity%20and%20Chain%20of%20Custody%20of%20Digital%20Evidence.pdf](https://www.ijmrset.com/upload/46_Blockchain%20and%20Deep%20Learning%20for%20Ensuring%20Integrity%20and%20Chain%20of%20Custody%20of%20Digital%20Evidence.pdf)  
23. Digital Evidence Management System Guide for Law Enforcement, accessed on January 1, 2026, [https://digitalevidence.ai/blog/digital-evidence-management-system-selection-guide](https://digitalevidence.ai/blog/digital-evidence-management-system-selection-guide)  
24. Buenas Prácticas En Informática Forense Para El Procesamiento De ..., accessed on January 1, 2026, [https://dialnet.unirioja.es/servlet/articulo?codigo=8660209](https://dialnet.unirioja.es/servlet/articulo?codigo=8660209)  
25. Digital Evidence Management System for Ensuring Chain of Custody, accessed on January 1, 2026, [https://vidizmo.ai/blog/digital-evidence-management-system-for-ensuring-chain-of-custody](https://vidizmo.ai/blog/digital-evidence-management-system-for-ensuring-chain-of-custody)  
26. Blockchain-Based Chain of Custody Evidence Management System ..., accessed on January 1, 2026, [https://www.scribd.com/document/694212197/Blockchain-Based-Chain-of-Custody-Evidence-Management-System-for-Digital-Forensic-Investigations](https://www.scribd.com/document/694212197/Blockchain-Based-Chain-of-Custody-Evidence-Management-System-for-Digital-Forensic-Investigations)  
27. How to extract image metadata in Python? \- GeeksforGeeks, accessed on January 1, 2026, [https://www.geeksforgeeks.org/python/how-to-extract-image-metadata-in-python/](https://www.geeksforgeeks.org/python/how-to-extract-image-metadata-in-python/)  
28. 13 Best OSINT (Open Source Intelligence) Tools for 2025 \- Talkwalker, accessed on January 1, 2026, [https://www.talkwalker.com/blog/best-osint-tools](https://www.talkwalker.com/blog/best-osint-tools)  
29. NEO4J How to make graph with relationships \- Stack Overflow, accessed on January 1, 2026, [https://stackoverflow.com/questions/68362728/neo4j-how-to-make-graph-with-relationships](https://stackoverflow.com/questions/68362728/neo4j-how-to-make-graph-with-relationships)  
30. Proteusiq/graphs: Exploring Neo4j with Python powered by Docker, accessed on January 1, 2026, [https://github.com/Proteusiq/graphs](https://github.com/Proteusiq/graphs)  
31. A Comparison between a Relational and a Graph Database in the ..., accessed on January 1, 2026, [https://www.researchgate.net/publication/354856815\_A\_Comparison\_between\_a\_Relational\_and\_a\_Graph\_Database\_in\_the\_Context\_of\_a\_Recommendation\_System](https://www.researchgate.net/publication/354856815_A_Comparison_between_a_Relational_and_a_Graph_Database_in_the_Context_of_a_Recommendation_System)  
32. No one uses Neo4j for actual large scale live applications... right?, accessed on January 1, 2026, [https://www.reddit.com/r/Neo4j/comments/18ygbwd/no\_one\_uses\_neo4j\_for\_actual\_large\_scale\_live/](https://www.reddit.com/r/Neo4j/comments/18ygbwd/no_one_uses_neo4j_for_actual_large_scale_live/)  
33. Detectives para seguir bajas por IT: diez sentencias a modo de ..., accessed on January 1, 2026, [https://detectiveseuropa.es/detectives-para-seguir-bajas-por-it-diez-sentencias-a-modo-de-ejemplo-la-no8-basada-en-una-investigacion-llevada-a-cabo-por-la-agencia-detectives-europa/](https://detectiveseuropa.es/detectives-para-seguir-bajas-por-it-diez-sentencias-a-modo-de-ejemplo-la-no8-basada-en-una-investigacion-llevada-a-cabo-por-la-agencia-detectives-europa/)  
34. Pillados por un detective o por Instagram: 9 sentencias de despidos ..., accessed on January 1, 2026, [https://www.bermejoialegret.com/pillados-por-un-detective-o-por-instagram-9-sentencias-de-despidos-procedentes-por-bajas-fraudulentas/](https://www.bermejoialegret.com/pillados-por-un-detective-o-por-instagram-9-sentencias-de-despidos-procedentes-por-bajas-fraudulentas/)  
35. vis.js Timeline time format \- Google Groups, accessed on January 1, 2026, [https://groups.google.com/g/tiddlywiki/c/OUJlcbbK5v0](https://groups.google.com/g/tiddlywiki/c/OUJlcbbK5v0)  
36. timeline \- vis.js \- A dynamic, browser based visualization library., accessed on January 1, 2026, [https://visjs.github.io/vis-timeline/docs/timeline/](https://visjs.github.io/vis-timeline/docs/timeline/)  
37. Vis-timeline \- Dash Example Index, accessed on January 1, 2026, [https://dash-example-index.herokuapp.com/vis-timeline](https://dash-example-index.herokuapp.com/vis-timeline)  
38. Comparison \- Abilian Innovation Lab, accessed on January 1, 2026, [https://lab.abilian.com/Tech/Python/Useful%20Libraries/Plugin%20Systems/Comparison/](https://lab.abilian.com/Tech/Python/Useful%20Libraries/Plugin%20Systems/Comparison/)  
39. Plugins \- Abilian Innovation Lab, accessed on January 1, 2026, [https://lab.abilian.com/Tech/Programming%20Techniques/Plugins/](https://lab.abilian.com/Tech/Programming%20Techniques/Plugins/)  
40. Entry Points \- setuptools 80.9.0 documentation, accessed on January 1, 2026, [https://setuptools.pypa.io/en/latest/userguide/entry\_point.html](https://setuptools.pypa.io/en/latest/userguide/entry_point.html)  
41. Writing Your First Forensic Tool-2: Extract Image Metadata with ..., accessed on January 1, 2026, [https://medium.com/@foysol60s/writing-your-first-forensic-tool-2-extract-image-metadata-with-python-image-library-faa70ac3b506](https://medium.com/@foysol60s/writing-your-first-forensic-tool-2-extract-image-metadata-with-python-image-library-faa70ac3b506)  
42. Investigating Embedded Metadata \- Tutorials Point, accessed on January 1, 2026, [https://www.tutorialspoint.com/python\_digital\_forensics/python\_digital\_forensics\_investigating\_embedded\_metadata.htm](https://www.tutorialspoint.com/python_digital_forensics/python_digital_forensics_investigating_embedded_metadata.htm)  
43. spanish-dni \- PyPI, accessed on January 1, 2026, [https://pypi.org/project/spanish-dni/](https://pypi.org/project/spanish-dni/)  
44. Validation of identity document Spain \- Google Developer forums, accessed on January 1, 2026, [https://discuss.google.dev/t/validation-of-identity-document-spain/57867](https://discuss.google.dev/t/validation-of-identity-document-spain/57867)  
45. stdnum.es.nif — python-stdnum 1.17 documentation \- Arthur de Jong, accessed on January 1, 2026, [https://arthurdejong.org/python-stdnum/doc/1.17/stdnum.es.nif](https://arthurdejong.org/python-stdnum/doc/1.17/stdnum.es.nif)  
46. Holehe OSINT \- Email to Registered Accounts \- GitHub, accessed on January 1, 2026, [https://github.com/megadose/holehe](https://github.com/megadose/holehe)  
47. osint-tools · GitHub Topics, accessed on January 1, 2026, [https://github.com/topics/osint-tools](https://github.com/topics/osint-tools)  
48. Best OSINT Tools for Intelligence Gathering (2025) Free and Paid, accessed on January 1, 2026, [https://shadowdragon.io/blog/best-osint-tools/](https://shadowdragon.io/blog/best-osint-tools/)  
49. ExifTool by Phil Harvey, accessed on January 1, 2026, [https://exiftool.org/](https://exiftool.org/)  
50. A Taxonomy of Python Libraries Helpful for Forensic Analysis, accessed on January 1, 2026, [https://www.giac.org/paper/gcfa/6879/grow-forensic-tools-taxonomy-python-libraries-helpful-forensic-analysis/121884](https://www.giac.org/paper/gcfa/6879/grow-forensic-tools-taxonomy-python-libraries-helpful-forensic-analysis/121884)  
51. python-stdnum \- PyPI, accessed on January 1, 2026, [https://pypi.org/project/python-stdnum/](https://pypi.org/project/python-stdnum/)  
52. 5 herramientas OSINT gratuitas para redes sociales \- We Live Security, accessed on January 1, 2026, [https://www.welivesecurity.com/la-es/2023/02/28/5-herramientas-osint-gratuitas-redes-sociales/](https://www.welivesecurity.com/la-es/2023/02/28/5-herramientas-osint-gratuitas-redes-sociales/)  
53. ¿Es legal que un detective privado le siga? Esto es lo que puede y ..., accessed on January 1, 2026, [https://detectivescabanach.com/es-legal-que-un-detective-privado-le-siga-esto-es-lo-que-puede-y-no-puede-hacer/](https://detectivescabanach.com/es-legal-que-un-detective-privado-le-siga-esto-es-lo-que-puede-y-no-puede-hacer/)  
54. Un detective es condenado por colocar un GPS en un coche para ..., accessed on January 1, 2026, [https://noticias.juridicas.com/actualidad/jurisprudencia/16331-un-detective-es-condenado-por-colocar-un-gps-en-un-coche-para-conseguir-pruebas/](https://noticias.juridicas.com/actualidad/jurisprudencia/16331-un-detective-es-condenado-por-colocar-un-gps-en-un-coche-para-conseguir-pruebas/)  
55. ¿Pueden usar localizadores GPS los detectives? | Privalia, accessed on January 1, 2026, [https://www.privaliadetectives.com/pueden-los-detectives-privados-usar-localizadores-gps-en-sus-investigaciones/](https://www.privaliadetectives.com/pueden-los-detectives-privados-usar-localizadores-gps-en-sus-investigaciones/)  
56. ¿PUEDE UN DETECTIVE PRIVADO COLOCAR UN DISPOSITIVO ..., accessed on January 1, 2026, [http://www.cmbabogados.com/blog/sts-278-2021](http://www.cmbabogados.com/blog/sts-278-2021)  
57. ¿Pueden los detectives privados usar localizadores GPS en sus ..., accessed on January 1, 2026, [https://detectib.com/pueden-los-detectives-privados-usar-localizadores-gps-en-sus-investigaciones/](https://detectib.com/pueden-los-detectives-privados-usar-localizadores-gps-en-sus-investigaciones/)  
58. Detectives y videovigilancia: una nueva variante en la cada vez más ..., accessed on January 1, 2026, [https://bloglaboral.garrigues.com/detectives-y-videovigilancia-control-trabajo](https://bloglaboral.garrigues.com/detectives-y-videovigilancia-control-trabajo)  
59. Marco Legal | Detectives Spain \- Detectives Spain, accessed on January 1, 2026, [https://detectives-spain.es/marco-legal/](https://detectives-spain.es/marco-legal/)  
60. Automating Disk Forensic Processing with SleuthKit, XML and Python, accessed on January 1, 2026, [https://apps.dtic.mil/sti/tr/pdf/ADA549270.pdf](https://apps.dtic.mil/sti/tr/pdf/ADA549270.pdf)  
61. Spanish IDs: NIF, NIE, CIF validators in grails \- Stack Overflow, accessed on January 1, 2026, [https://stackoverflow.com/questions/34438372/spanish-ids-nif-nie-cif-validators-in-grails](https://stackoverflow.com/questions/34438372/spanish-ids-nif-nie-cif-validators-in-grails)