# Propuesta inicial

**Estado:** borrador para conversar con el compañero y decidir juntos si eligen este tema. La conformidad del compañero todavía está pendiente. El detalle sigue la estructura de la sección 12 de la [consigna](../01-fuentes/consignas/Trabajo_Final_Consigna.pdf); una eventual presentación a la cátedra sería un paso posterior.

## Título provisorio

**Planificación de personal para la preparación de pedidos de un supermercado online mediante pronósticos y teoría de colas.**

## La idea en pocas palabras: para conversar en equipo

Tomaríamos como contexto el supermercado del ERP que desarrollamos. Nos pondríamos en el lugar de un gerente que necesita responder: **«¿Cuántas personas necesito preparando pedidos online para que estén listos a tiempo?»**

El recorrido de cada pedido sería: **entra al sistema → espera si todos están ocupados → una persona lo prepara → queda listo para retirar o despachar**. Estudiaríamos cómo cambia ese recorrido cuando llegan más pedidos o cuando hay más empleados disponibles.

### Qué haríamos, paso a paso

| Paso | Qué haríamos en términos simples | Qué obtendríamos |
| :---- | :---- | :---- |
| 1\. Revisar el histórico | Separar los pedidos online y contar cuántos llegaron en cada hora. Revisar cómo se generaron los datos sintéticos del ERP. | Un panorama de la demanda y de los datos que podemos aprovechar. |
| 2\. Estimar la demanda futura | Usar métodos sencillos para anticipar cuántos pedidos podrían llegar al día siguiente, por hora. Comprobar sus errores con una parte del histórico reservada para evaluarlos. | Un pronóstico acompañado de una medida de cuánto se equivoca. |
| 3\. Representar la preparación | Definir cómo esperan los pedidos, cómo se asignan a empleados y cuánto tarda su preparación. Los tiempos que falten se generarían con supuestos documentados. | Un modelo explícito del proceso y sus límites. |
| 4\. Probar alternativas | Programar una simulación y repetir jornadas de demanda baja, media y alta con distintas cantidades de empleados. Por ejemplo, comparar uno, dos y tres preparadores, ajustando esas cantidades a la escala de los datos. | Resultados comparables sobre esperas, pedidos acumulados y ocupación del personal. |
| 5\. Sacar una conclusión | Elegir, entre las alternativas evaluadas, la menor cantidad de empleados que cumpla el objetivo de tiempo definido para cada escenario. | Una recomendación respaldada por tablas y gráficos, indicando cuándo podría cambiar. |

Las técnicas se conectarían así: **el pronóstico anticipa los pedidos; la teoría de colas ayuda a entender la relación entre demanda, capacidad y espera; la simulación permite experimentar con distintas configuraciones**.

El producto práctico sería un programa de análisis en Python, acompañado por los datos, los gráficos y un informe que explique la recomendación. El ERP aporta el contexto y el histórico sintético; una integración futura podría mostrar estos resultados en el tablero gerencial. El estudio abarcaría hasta que el pedido queda preparado.

Este resumen describe lo que proponemos hacer. Las cantidades de empleados son ejemplos de configuraciones, y los resultados se conocerán al ejecutar los experimentos. La primera decisión entre compañeros es si les interesa trabajar sobre esta pregunta; los métodos se estudiarán y explicarán durante el desarrollo.

## Integrantes

Dos estudiantes. Nombres y apellidos pendientes de completar.

## Modalidad y unidades involucradas

**Modalidad A — Aplicación práctica.** Integración de **Pronósticos y Teoría de Colas**, apoyada en simulación de eventos discretos.

## Problema y contexto

El equipo desarrolló durante Sistemas III un ERP de supermercado con ventas, cajas, inventario, depósitos y transferencias, compras, proveedores, e-commerce y un tablero gerencial. Este trabajo tomará ese contexto para estudiar la preparación de pedidos online.

Cuando la llegada de pedidos supera la capacidad de los empleados disponibles, se acumulan pedidos y aumenta el tiempo hasta que quedan preparados. Una dotación mayor puede reducir esas demoras, pero también dejar recursos ociosos durante períodos de menor demanda.

La pregunta central será: **¿cuántos preparadores conviene asignar para atender distintos niveles de demanda y cumplir un objetivo de tiempo de preparación?**

## Objetivo general

Desarrollar y evaluar un modelo de apoyo a la decisión que combine el pronóstico de pedidos con el análisis de colas y la simulación para recomendar una dotación de preparadores bajo distintos escenarios de demanda.

## Técnicas previstas y aplicación práctica

El proceso estudiado será: **llegada del pedido → espera → preparación por un empleado → pedido listo**.

1. **Preparar los datos.** Identificar pedidos online, revisar fechas y horarios y construir una serie de cantidad de pedidos por hora. Confirmar qué registro representa la llegada del pedido al proceso.  
2. **Pronosticar la demanda.** Comparar una referencia sencilla —repetir la demanda de la misma hora de la semana anterior— con un promedio de esa hora y día en semanas recientes. Evaluar el error absoluto medio (MAE) respetando el orden temporal y reservando un período final para la prueba. La referencia estacional y la evaluación con datos no usados para ajustar el modelo se apoyan en Hyndman y Athanasopoulos \[1\].  
3. **Modelar la cola.** Representar una fila común de pedidos, atendidos por orden de llegada, con varios preparadores equivalentes. Cada empleado preparará un pedido a la vez. Documentar los supuestos de llegadas y duración del servicio; usar un caso M/M/c de tasas constantes como referencia analítica cuando se cumplan sus condiciones.  
4. **Simular y comparar.** Usar el perfil horario pronosticado para simular jornadas con dotaciones alternativas, manteniendo la dotación fija durante cada jornada simulada. Conservar entre horas los pedidos pendientes y repetir los experimentos con semillas aleatorias registradas. SimPy permite representar recursos de capacidad limitada y las esperas por utilizarlos \[2\].  
5. **Recomendar una dotación.** Comparar demanda baja, media y alta mediante espera promedio, tiempo total hasta que el pedido queda listo, longitud de cola, utilización del personal y porcentaje de pedidos que cumplen el tiempo objetivo. Identificar la menor dotación, entre las evaluadas, que alcance ese objetivo; informar también los casos en los que ninguna lo cumpla.

El tiempo objetivo y los niveles de demanda serán parámetros explícitos del experimento, definidos y justificados antes de comparar resultados. Se estudiará la sensibilidad de la recomendación frente a errores de pronóstico y cambios en los tiempos de preparación.

## Herramientas

Python, con pandas para preparar datos, SimPy para simular y Matplotlib para visualizar resultados. Se entregarán scripts reproducibles con dependencias e instrucciones de ejecución. La investigación se documentará en Markdown y el informe final en LaTeX.

## Datos y supuestos

Según lo informado por el equipo, el ERP dispone de un histórico sintético de aproximadamente seis meses, generado para su tablero gerencial, que distingue ventas presenciales y online e incluye fechas y horarios. El generador y los registros todavía deben inspeccionarse: su volumen, sus patrones y la correspondencia entre ventas y pedidos no están verificados.

Se prevé aprovechar esos datos y, si resulta necesario, adaptar una copia del generador, conservando el original y documentando parámetros y semillas. Si faltan tiempos de preparación, se generarán mediante supuestos explícitos y se variarán en los experimentos. Las conclusiones se referirán al sistema modelado y a sus datos sintéticos.

## Verificación, validación y alcance

La simulación se verificará con casos simples y un caso estable de tasas constantes con solución analítica. Se comprobará la conservación de pedidos y la coherencia de tiempos y unidades. Los resultados de una jornada con demanda variable se analizarán mediante simulación, distinguiéndolos de las fórmulas de régimen estacionario. Se evaluará además cómo cambia el servicio al variar demanda y capacidad, y la dotación recomendada se contrastará con pedidos del período de prueba.

El estudio abarcará hasta que los pedidos queden preparados. Se asumirá disponibilidad de productos y empleados equivalentes. El ruteo dentro del depósito, reparto, turnos laborales y faltantes quedan fuera del modelo inicial. El producto será un análisis computacional independiente inspirado en el ERP; la integración con el tablero gerencial queda como posible extensión.

## Resultados esperados

- Pronóstico de cantidad de pedidos con evaluación de su error.  
- Simulador reproducible y comparación sistemática de al menos tres escenarios.  
- Tablas y gráficos de espera, acumulación y utilización del personal.  
- Recomendación de dotación con sus supuestos, incertidumbre y limitaciones.  
- Informe final en LaTeX/PDF, código y datos necesarios para reproducir el estudio.

## Organización orientativa

El plazo informado es de dos semanas, compartidas con otras materias. Durante la primera se prevé revisar datos, estudiar los fundamentos e implementar y verificar los modelos; durante la segunda, ejecutar experimentos, analizar resultados, redactar y preparar la defensa. El inicio del desarrollo definitivo queda sujeto a la aprobación de la cátedra. El alcance deberá ajustarse si los datos o la disponibilidad efectiva lo requieren.

## Referencias iniciales

1. Hyndman, R. J., y Athanasopoulos, G. *Forecasting: Principles and Practice*, 3.ª edición, capítulo 5\. [Métodos de referencia y evaluación de pronósticos](https://otexts.com/fpp3/toolbox.html). Clave: `hyndman_athanasopoulos_fpp3`.  
2. Documentación oficial de SimPy. [Shared Resources](https://simpy.readthedocs.io/en/stable/topical_guides/resources.html). Clave: `simpy_shared_resources`.

Las referencias iniciales se ampliarán con bibliografía académica de teoría de colas y de la materia.

## Revisión del equipo

Pendiente de conversar con el compañero y acordar el tema y su alcance. Este documento es el material para esa conversación.

## Aprobación de la cátedra

Paso posterior al acuerdo del equipo, según lo requerido por la consigna. Registrar aquí fecha, devolución y eventuales ajustes cuando se obtenga.