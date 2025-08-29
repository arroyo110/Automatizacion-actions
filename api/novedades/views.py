from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta, time
from .models import Novedad
from .serializers import NovedadSerializer, NovedadDetailSerializer, NovedadUpdateEstadoSerializer
from api.manicuristas.models import Manicurista
from api.manicuristas.serializers import ManicuristaSerializer
from api.citas.models import Cita # Importar el modelo Cita
from django.core.mail import send_mail
from django.conf import settings


class NovedadViewSet(viewsets.ModelViewSet):
    queryset = Novedad.objects.all()
    serializer_class = NovedadSerializer

    def get_queryset(self):
        queryset = Novedad.objects.select_related('manicurista').all()

        # Filtros
        manicurista_id = self.request.query_params.get('manicurista')
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')
        estado = self.request.query_params.get('estado')
        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')

        if manicurista_id:
            queryset = queryset.filter(manicurista_id=manicurista_id)
        if fecha_inicio:
            queryset = queryset.filter(fecha__gte=fecha_inicio)
        if fecha_fin:
            queryset = queryset.filter(fecha__lte=fecha_fin)
        if estado:
            queryset = queryset.filter(estado=estado)
        if fecha_desde:
            try:
                fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha__gte=fecha_desde)
            except ValueError:
                pass
        if fecha_hasta:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha__lte=fecha_hasta)
            except ValueError:
                pass

        return queryset.order_by('-fecha', 'manicurista__nombre') # Corregido a 'manicurista__nombre'

    def get_serializer_class(self):
        if self.action in ['retrieve', 'list']:
            return NovedadDetailSerializer
        elif self.action == 'actualizar_estado':
            return NovedadUpdateEstadoSerializer
        return NovedadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the cache on the instance, otherwise the
            # 'to_representation' method may still see the old related objects.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def anular(self, request, pk=None):
        """Anular una novedad con motivo"""
        try:
            novedad = self.get_object()
            motivo_anulacion = request.data.get('motivo_anulacion')
            
            if not motivo_anulacion:
                return Response(
                    {'error': 'El motivo de anulación es requerido'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Anular la novedad
            novedad.estado = 'anulada'
            novedad.motivo_anulacion = motivo_anulacion
            novedad.fecha_anulacion = timezone.now()
            novedad.save()
            
            # Reactivar citas que fueron canceladas por esta novedad
            self._reactivar_citas_canceladas(novedad)
            
            detail_serializer = NovedadDetailSerializer(novedad)
            return Response({
                'message': 'Novedad anulada exitosamente',
                'data': detail_serializer.data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['patch'])
    def actualizar_estado(self, request, pk=None):
        novedad = self.get_object()
        serializer = self.get_serializer(novedad, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def disponibilidad_citas(self, request):
        """
        Verificar disponibilidad de horarios para citas considerando novedades y citas existentes.
        Devuelve una lista de slots de 30 minutos con su estado (disponible/ocupado) y motivo.
        """
        manicurista_id = request.query_params.get('manicurista')
        fecha_str = request.query_params.get('fecha')
        
        if not manicurista_id or not fecha_str:
            return Response(
                {'error': 'Se requiere manicurista y fecha'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            
            # 1. Obtener horario base del día
            horario_base_inicio = Novedad.HORA_ENTRADA_BASE
            horario_base_fin = Novedad.HORA_SALIDA_BASE

            # Lista para almacenar los slots ocupados
            slots_ocupados = []

            # 2. Obtener novedades activas para esa manicurista en esa fecha
            novedades = Novedad.objects.filter(
                manicurista_id=manicurista_id,
                fecha=fecha,
                estado__in=['ausente', 'tardanza']
            )
            
            for novedad in novedades:
                if novedad.estado == 'ausente':
                    if novedad.tipo_ausencia == 'completa':
                        # Ausencia completa: ocupa todo el horario base
                        slots_ocupados.append({
                            'inicio': horario_base_inicio,
                            'fin': horario_base_fin,
                            'motivo': f"Ausencia completa: {novedad.observaciones or 'Sin motivo'}" # Usar observaciones
                        })
                    elif novedad.tipo_ausencia == 'por_horas':
                        # Ausencia por horas
                        slots_ocupados.append({
                            'inicio': novedad.hora_inicio_ausencia,
                            'fin': novedad.hora_fin_ausencia,
                            'motivo': f"Ausencia por horas: {novedad.observaciones or 'Sin motivo'}" # Usar observaciones
                        })
                elif novedad.estado == 'tardanza':
                    # Tardanza: ocupa desde el inicio del horario base hasta la hora de llegada
                    slots_ocupados.append({
                        'inicio': horario_base_inicio,
                        'fin': novedad.hora_entrada,
                        'motivo': f"Tardanza: llega a las {novedad.hora_entrada.strftime('%H:%M')}"
                    })
            
            # 3. Obtener citas existentes para esa manicurista en esa fecha
            citas = Cita.objects.filter(
                manicurista_id=manicurista_id,
                fecha_cita=fecha,
                estado__in=['pendiente', 'en_proceso'] # Citas que ocupan tiempo
            )
            
            for cita in citas:
                # Usar duracion_total del modelo Cita
                duracion_cita_minutos = cita.duracion_total
                
                cita_inicio_dt = datetime.combine(fecha, cita.hora_cita)
                cita_fin_dt = cita_inicio_dt + timedelta(minutes=duracion_cita_minutos)
                
                slots_ocupados.append({
                    'inicio': cita_inicio_dt.time(),
                    'fin': cita_fin_dt.time(),
                    'motivo': f"Cita agendada con {cita.cliente.nombre if hasattr(cita, 'cliente') else 'Cliente'}"
                })

            # 4. Generar todos los slots de 30 minutos en el horario base
            intervalo_minutos = 30
            horarios_disponibles_response = []
            
            current_time = datetime.combine(fecha, horario_base_inicio)
            end_time = datetime.combine(fecha, horario_base_fin)

            while current_time < end_time:
                slot_inicio = current_time.time()
                slot_fin = (current_time + timedelta(minutes=intervalo_minutos)).time()
                
                is_available = True
                motivo_ocupado = None

                # Verificar si este slot se solapa con algún slot ocupado
                for ocupado in slots_ocupados:
                    ocupado_inicio_dt = datetime.combine(fecha, ocupado['inicio'])
                    ocupado_fin_dt = datetime.combine(fecha, ocupado['fin'])
                    
                    slot_inicio_dt = datetime.combine(fecha, slot_inicio)
                    slot_fin_dt = datetime.combine(fecha, slot_fin)

                    # Comprobar solapamiento
                    if (slot_inicio_dt < ocupado_fin_dt and slot_fin_dt > ocupado_inicio_dt):
                        is_available = False
                        motivo_ocupado = ocupado['motivo']
                        break
                
                horarios_disponibles_response.append({
                    'slot': f"{slot_inicio.strftime('%H:%M')}-{slot_fin.strftime('%H:%M')}",
                    'inicio': slot_inicio.strftime('%H:%M'),
                    'fin': slot_fin.strftime('%H:%M'),
                    'disponible': is_available,
                    'motivo_ocupado': motivo_ocupado
                })
                
                current_time += timedelta(minutes=intervalo_minutos)
            
            return Response({
                'fecha': fecha_str,
                'manicurista_id': manicurista_id,
                'horario_base': {
                    'entrada': horario_base_inicio.strftime('%H:%M'),
                    'salida': horario_base_fin.strftime('%H:%M')
                },
                'slots_disponibilidad': horarios_disponibles_response,
                'mensaje': 'Disponibilidad calculada exitosamente'
            })
            
        except ValueError:
            return Response(
                {'error': 'Formato de fecha inválido. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print(f"Error en disponibilidad_citas: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def novedades_hoy(self, request):
        """Obtener novedades registradas para el día actual."""
        hoy = timezone.now().date()
        novedades_hoy = self.get_queryset().filter(fecha=hoy)
        serializer = self.get_serializer(novedades_hoy, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def novedades_activas(self, request):
        """Obtener novedades que no están anuladas."""
        novedades_activas = self.get_queryset().exclude(estado='anulada')
        serializer = self.get_serializer(novedades_activas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def manicuristas_con_novedades(self, request):
        """Obtener manicuristas que tienen novedades registradas."""
        manicuristas_ids = Novedad.objects.values_list('manicurista', flat=True).distinct()
        manicuristas = Manicurista.objects.filter(id__in=manicuristas_ids).order_by('nombre')
        serializer = ManicuristaSerializer(manicuristas, many=True)
        return Response(serializer.data)

    def _manejar_citas_afectadas(self, novedad):
        """Manejar citas afectadas por la novedad"""
        try:
            # Buscar citas activas para esa manicurista en esa fecha
            citas_afectadas = Cita.objects.filter(
                manicurista=novedad.manicurista,
                fecha_cita=novedad.fecha,
                estado__in=['pendiente', 'en_proceso'] # Solo citas pendientes o en proceso
            )

            for cita in citas_afectadas:
                # Verificar si la cita está en el horario afectado
                if self._cita_en_horario_afectado(cita, novedad):
                    # Cancelar la cita
                    cita.estado = 'cancelada_por_novedad'
                    cita.motivo_cancelacion = f"Novedad de manicurista: {novedad.get_estado_display()} - {novedad.observaciones or 'Sin motivo'}"
                    cita.novedad_relacionada = novedad
                    cita.save()

                    # Enviar notificación al cliente
                    self._notificar_cliente_cancelacion(cita, novedad)
                    
        except Exception as e:
            print(f"Error manejando citas afectadas: {e}")

    def _cita_en_horario_afectado(self, cita, novedad):
        """Verificar si una cita está en el horario afectado por la novedad"""
        # Convertir horas a objetos datetime para comparación precisa
        fecha_cita_dt = datetime.combine(cita.fecha_cita, time(0,0)) # Usar la fecha de la cita para combinar
        
        cita_inicio_dt = datetime.combine(fecha_cita_dt, cita.hora_cita)
        # Usar duracion_total del modelo Cita
        duracion_cita_minutos = cita.duracion_total
        cita_fin_dt = cita_inicio_dt + timedelta(minutes=duracion_cita_minutos)

        if novedad.estado == 'ausente':
            if novedad.tipo_ausencia == 'completa':
                return True  # Toda la jornada afectada
            elif novedad.tipo_ausencia == 'por_horas':
                novedad_inicio_dt = datetime.combine(fecha_cita_dt, novedad.hora_inicio_ausencia)
                novedad_fin_dt = datetime.combine(fecha_cita_dt, novedad.hora_fin_ausencia)
                # Comprobar solapamiento: (A_inicio < B_fin) and (A_fin > B_inicio)
                return (cita_inicio_dt < novedad_fin_dt and cita_fin_dt > novedad_inicio_dt)
        
        elif novedad.estado == 'tardanza':
            novedad_llegada_dt = datetime.combine(fecha_cita_dt, novedad.hora_entrada)
            # Si la cita se solapa con el periodo de tardanza (es decir, la cita empieza antes de la llegada)
            return cita_inicio_dt < novedad_llegada_dt
        
        return False

    def _reactivar_citas_canceladas(self, novedad):
        """Reactivar citas que fueron canceladas por esta novedad"""
        try:
            citas_canceladas = Cita.objects.filter(
                novedad_relacionada=novedad,
                estado='cancelada_por_novedad'
            )
            
            for cita in citas_canceladas:
                cita.estado = 'pendiente' # O el estado original que tenía antes de la cancelación
                cita.motivo_cancelacion = None
                cita.novedad_relacionada = None
                cita.save()
                
                # Notificar al cliente que su cita fue reactivada
                self._notificar_cliente_reactivacion(cita)
                
        except Exception as e:
            print(f"Error reactivando citas: {e}")

    def _notificar_cliente_cancelacion(self, cita, novedad):
        """Notificar al cliente sobre la cancelación de su cita"""
        try:
            # Asegúrate de que cita.cliente y cita.cliente.email existan
            if hasattr(cita, 'cliente') and cita.cliente and hasattr(cita.cliente, 'email') and cita.cliente.email:
                send_mail(
                    subject='Cancelación de tu cita en Spa',
                    message=f"Hola {cita.cliente.nombre},\n\n"
                            f"Lamentamos informarte que tu cita con {novedad.manicurista.nombre} " # Usar .nombre
                            f"el {novedad.fecha.strftime('%d/%m/%Y')} a las {cita.hora_cita.strftime('%H:%M')} "
                            f"ha sido cancelada debido a una novedad de la manicurista.\n\n"
                            f"Motivo: {novedad.get_estado_display()} - {novedad.observaciones or 'Sin motivo'}\n\n"
                            f"Te invitamos a agendar una nueva cita desde nuestra plataforma.\n\n"
                            f"Gracias por tu comprensión.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[cita.cliente.email],
                    fail_silently=True
                )
        except Exception as e:
            print(f"Error enviando notificación de cancelación: {e}")

    def _notificar_cliente_reactivacion(self, cita):
        """Notificar al cliente que su cita fue reactivada"""
        try:
            # Asegúrate de que cita.cliente y cita.cliente.email existan
            if hasattr(cita, 'cliente') and cita.cliente and hasattr(cita.cliente, 'email') and cita.cliente.email:
                send_mail(
                    subject='Tu cita ha sido reactivada',
                    message=f"Hola {cita.cliente.nombre},\n\n"
                            f"Te informamos que tu cita con {cita.manicurista.nombre} " # Usar .nombre
                            f"el {cita.fecha_cita.strftime('%d/%m/%Y')} a las {cita.hora_cita.strftime('%H:%M')} "
                            f"ha sido reactivada.\n\n"
                            f"La novedad que causó la cancelación ha sido anulada.\n\n"
                            f"Tu cita está confirmada nuevamente.\n\n"
                            f"¡Te esperamos!",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[cita.cliente.email],
                    fail_silently=True
                )
        except Exception as e:
            print(f"Error enviando notificación de reactivación: {e}")
