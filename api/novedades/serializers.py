from rest_framework import serializers
from api.novedades.models import Novedad
from api.manicuristas.serializers import ManicuristaSerializer
from datetime import time, date, timedelta, datetime
from django.utils.timezone import localdate, make_aware, get_default_timezone


class NovedadSerializer(serializers.ModelSerializer):
  manicurista_info = ManicuristaSerializer(source='manicurista', read_only=True)
  
  class Meta:
      model = Novedad
      fields = '__all__'

  def validate_fecha(self, value):
      # Forzar que siempre sea una fecha local, sin hora
      if isinstance(value, datetime):
          value = localdate(value)
      return value

  def validate_manicurista(self, value):
      if not value:
          raise serializers.ValidationError("Debe seleccionar una manicurista.")
      return value

  def validate_estado(self, value):
      if not value:
          raise serializers.ValidationError("Debe seleccionar un estado.")
      return value

  def validate_hora_entrada(self, value):
      if value and not (Novedad.HORA_MIN_PERMITIDA <= value <= Novedad.HORA_MAX_PERMITIDA):
          raise serializers.ValidationError(
              f"La hora de entrada debe estar entre {Novedad.HORA_MIN_PERMITIDA.strftime('%H:%M')} "
              f"y {Novedad.HORA_MAX_PERMITIDA.strftime('%H:%M')}."
          )
      return value

  def validate_hora_inicio_ausencia(self, value):
      if value and not (Novedad.HORA_MIN_PERMITIDA <= value <= Novedad.HORA_MAX_PERMITIDA):
          raise serializers.ValidationError(
              f"La hora de inicio debe estar entre {Novedad.HORA_MIN_PERMITIDA.strftime('%H:%M')} "
              f"y {Novedad.HORA_MAX_PERMITIDA.strftime('%H:%M')}."
          )
      return value

  def validate_hora_fin_ausencia(self, value):
      if value and not (Novedad.HORA_MIN_PERMITIDA <= value <= Novedad.HORA_MAX_PERMITIDA):
          raise serializers.ValidationError(
              f"La hora de fin debe estar entre {Novedad.HORA_MIN_PERMITIDA.strftime('%H:%M')} "
              f"y {Novedad.HORA_MAX_PERMITIDA.strftime('%H:%M')}."
          )
      return value

  def validate(self, data):
      """
      Validaciones a nivel de objeto para asegurar la consistencia de los datos
      basado en el estado de la novedad.
      """
      estado = data.get('estado')
      hora_entrada = data.get('hora_entrada')
      tipo_ausencia = data.get('tipo_ausencia')
      hora_inicio_ausencia = data.get('hora_inicio_ausencia')
      hora_fin_ausencia = data.get('hora_fin_ausencia')

      if estado == 'tardanza':
          if not hora_entrada:
              raise serializers.ValidationError({'hora_entrada': 'La hora de entrada es requerida para el estado "Tardanza".'})
          if hora_entrada < time(10, 0) or hora_entrada > time(20, 0):
              raise serializers.ValidationError({'hora_entrada': 'La hora de entrada debe estar entre 10:00 AM y 8:00 PM.'})
          # Asegurarse de que los campos de ausencia no estén presentes o sean nulos
          if tipo_ausencia or hora_inicio_ausencia or hora_fin_ausencia:
              raise serializers.ValidationError('Los campos de ausencia no deben especificarse para el estado "Tardanza".')
      elif estado == 'ausente':
          if not tipo_ausencia:
              raise serializers.ValidationError({'tipo_ausencia': 'El tipo de ausencia es requerido para el estado "Ausente".'})
          if tipo_ausencia == 'por_horas':
              if not hora_inicio_ausencia or not hora_fin_ausencia:
                  raise serializers.ValidationError('Las horas de inicio y fin de ausencia son requeridas para el tipo "Por Horas".')
              if hora_inicio_ausencia >= hora_fin_ausencia:
                  raise serializers.ValidationError('La hora de inicio de ausencia debe ser anterior a la hora de fin.')
              if hora_inicio_ausencia < time(10, 0) or hora_fin_ausencia > time(20, 0):
                  raise serializers.ValidationError('Las horas de ausencia deben estar dentro del horario de 10:00 AM a 8:00 PM.')
          elif tipo_ausencia == 'completa':
              if hora_inicio_ausencia or hora_fin_ausencia:
                  raise serializers.ValidationError('Las horas de inicio y fin de ausencia no deben especificarse para el tipo "Día Completo".')
          # Asegurarse de que el campo de tardanza no esté presente o sea nulo
          if hora_entrada:
              raise serializers.ValidationError('La hora de entrada no debe especificarse para el estado "Ausente".')
      else: # 'normal' o 'anulada'
          # Asegurarse de que ningún campo específico de tardanza/ausencia esté presente
          if hora_entrada or tipo_ausencia or hora_inicio_ausencia or hora_fin_ausencia:
              raise serializers.ValidationError('No se deben especificar campos de tardanza o ausencia para el estado "Normal" o "Anulada".')

      # Obtener la instancia actual si es una actualización
      instance = self.instance
      
      fecha = data.get('fecha')
      manicurista = data.get('manicurista')

      today = localdate()
      tomorrow = today + timedelta(days=1)

      # Validación de fecha según el estado
      if fecha and estado:
          if estado == 'ausente' and fecha < tomorrow:
              raise serializers.ValidationError({
                  'fecha': 'Para ausencias, debe seleccionar una fecha a partir de mañana.'
              })
          elif estado == 'tardanza' and fecha < today:
              raise serializers.ValidationError({
                  'fecha': 'Para tardanzas, debe seleccionar una fecha a partir de hoy.'
              })
          elif fecha < today: # Validación general para cualquier novedad no anulada
              raise serializers.ValidationError({
                  'fecha': 'No se puede registrar una novedad en fecha anterior a hoy.'
              })

      # Validación de duplicados activos
      # Solo validar si no es una novedad anulada
      if estado != 'anulada':
          existing_query = Novedad.objects.filter(
              manicurista=manicurista,
              fecha=fecha
          ).exclude(estado='anulada')
          
          if instance and instance.pk: # Si es una actualización, excluir la instancia actual
              existing_query = existing_query.exclude(pk=instance.pk)
              
          if existing_query.exists():
              raise serializers.ValidationError(
                  "Ya existe una novedad activa para esta manicurista en la fecha indicada."
              )

      return data


class NovedadDetailSerializer(serializers.ModelSerializer):
  manicurista = ManicuristaSerializer(read_only=True)
  mensaje_personalizado = serializers.SerializerMethodField()
  horario_base = serializers.SerializerMethodField()
  validacion_fecha = serializers.SerializerMethodField()
  citas_afectadas = serializers.SerializerMethodField()

  class Meta:
      model = Novedad
      fields = '__all__'

  def get_horario_base(self, obj):
      return {
          'entrada': Novedad.HORA_ENTRADA_BASE.strftime('%H:%M'),
          'salida': Novedad.HORA_SALIDA_BASE.strftime('%H:%M')
      }

  def get_validacion_fecha(self, obj):
      today = localdate()
      tomorrow = today + timedelta(days=1)
      return {
          'hoy': today.isoformat(),
          'manana': tomorrow.isoformat(),
          'reglas': {
              'ausente': 'Debe programarse con al menos un día de anticipación (desde mañana)',
              'tardanza': 'Puede registrarse desde hoy'
          }
      }

  def get_mensaje_personalizado(self, obj):
      nombre = obj.manicurista.nombre if obj.manicurista else "Manicurista" # Usar .nombre
      if obj.estado == 'tardanza':
          if obj.hora_entrada:
              return f"La manicurista {nombre} llegó tarde a las {obj.hora_entrada.strftime('%I:%M %p')}."
          else:
              return f"La manicurista {nombre} llegó tarde, sin hora registrada."
      elif obj.estado == 'ausente':
          if obj.tipo_ausencia == 'completa':
              return f"La manicurista {nombre} se ausentó todo el día ({Novedad.HORA_ENTRADA_BASE.strftime('%I:%M %p')} - {Novedad.HORA_SALIDA_BASE.strftime('%I:%M %p')})."
          elif obj.tipo_ausencia == 'por_horas':
              if obj.hora_inicio_ausencia and obj.hora_fin_ausencia:
                  return (f"La manicurista {nombre} se ausentó desde "
                          f"{obj.hora_inicio_ausencia.strftime('%I:%M %p')} hasta "
                          f"{obj.hora_fin_ausencia.strftime('%I:%M %p')}.")
              else:
                  return f"La manicurista {nombre} se ausenta por horas, sin horario definido."
      elif obj.estado == 'anulada':
          return f"Novedad de {nombre} anulada: {obj.motivo_anulacion}"
      return f"La manicurista {nombre} tiene una novedad registrada."

  def get_citas_afectadas(self, obj):
      """Obtener información de citas afectadas por esta novedad"""
      try:
          from api.citas.models import Cita
          citas = Cita.objects.filter(
              novedad_relacionada=obj # Usar el nuevo campo
          ).values('id', 'hora_cita', 'estado', 'cliente__nombre')
          return list(citas)
      except Exception as e:
          # Manejar el error si el modelo Cita no está disponible o hay otro problema
          print(f"Error al obtener citas afectadas: {e}")
          return []


class NovedadUpdateEstadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Novedad
        fields = ['estado', 'observaciones']

    def validate_estado(self, value):
        """Validar transiciones de estado válidas."""
        if self.instance:
            estado_actual = self.instance.estado
            transiciones_validas = {
                'normal': ['tardanza', 'ausente', 'anulada'],
                'tardanza': ['normal', 'ausente', 'anulada'],
                'ausente': ['normal', 'tardanza', 'anulada'],
                'anulada': [], # No se puede cambiar desde anulada
            }
            if value not in transiciones_validas.get(estado_actual, []):
                raise serializers.ValidationError(
                    f"No se puede cambiar de '{estado_actual}' a '{value}'"
                )
        return value
