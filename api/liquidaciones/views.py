from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Sum, Q
from datetime import datetime
from .models import Liquidacion
from .serializers import (
    LiquidacionSerializer, 
    LiquidacionDetailSerializer, 
    LiquidacionCreateSerializer,
    LiquidacionUpdateSerializer
)
from api.citas.models import Cita
from api.manicuristas.models import Manicurista

# CORREGIDO: Importar desde el módulo correcto
try:
    from api.ventaservicios.models import VentaServicio
except ImportError:
    try:
        from api.ventaservicios.models import VentaServicio
    except ImportError:
        # Si no existe ninguno de los dos, crear una clase dummy
        class VentaServicio:
            objects = None
            
            @classmethod
            def filter(cls, **kwargs):
                return cls.objects.none() if cls.objects else []


class LiquidacionViewSet(viewsets.ModelViewSet):
    queryset = Liquidacion.objects.all()
    serializer_class = LiquidacionSerializer

    def get_serializer_class(self):
        if self.action in ['retrieve', 'list']:
            return LiquidacionDetailSerializer
        elif self.action == 'create':
            return LiquidacionCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return LiquidacionUpdateSerializer
        return LiquidacionSerializer

    def get_queryset(self):
        queryset = Liquidacion.objects.select_related('manicurista').all()
        manicurista_id = self.request.query_params.get('manicurista')
        estado = self.request.query_params.get('estado')
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_final = self.request.query_params.get('fecha_final')

        if manicurista_id:
            queryset = queryset.filter(manicurista_id=manicurista_id)
        if estado:
            queryset = queryset.filter(estado=estado)
        if fecha_inicio and fecha_final:
            queryset = queryset.filter(fecha_inicio=fecha_inicio, fecha_final=fecha_final)

        return queryset.order_by('-fecha_inicio')

    @action(detail=False, methods=['post'])
    def calcular_valor_ventas(self, request):
        """
        Calcular el total de ventas completadas para una manicurista en un período
        """
        manicurista_id = request.data.get('manicurista_id')
        fecha_inicio = request.data.get('fecha_inicio')
        fecha_final = request.data.get('fecha_final')

        if not all([manicurista_id, fecha_inicio, fecha_final]):
            return Response({
                "error": "Se requieren manicurista_id, fecha_inicio y fecha_final"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            manicurista = Manicurista.objects.get(id=manicurista_id)
        except Manicurista.DoesNotExist:
            return Response({"error": "Manicurista no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Convertir fechas string a objetos date
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            fecha_final_obj = datetime.strptime(fecha_final, '%Y-%m-%d').date()
        except ValueError:
            return Response({"error": "Formato de fecha inválido. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar si el modelo VentaServicio existe y tiene datos
        try:
            if hasattr(VentaServicio, 'objects') and VentaServicio.objects is not None:
                # Calcular ventas completadas (pagadas) en el período
                ventas_completadas = VentaServicio.objects.filter(
                    manicurista=manicurista,
                    fecha_venta__date__range=(fecha_inicio_obj, fecha_final_obj),
                    estado='pagada'
                ).select_related('cliente', 'servicio')

                # Calcular totales
                total_ventas = ventas_completadas.aggregate(
                    total=Sum('total')
                )['total'] or 0

                cantidad_ventas = ventas_completadas.count()

                # Obtener detalles de las ventas
                ventas_detalle = []
                for venta in ventas_completadas:
                    ventas_detalle.append({
                        'id': venta.id,
                        'fecha': venta.fecha_venta.date(),
                        'cliente': venta.cliente.nombre if venta.cliente else 'Cliente no disponible',
                        'servicio': venta.servicio.nombre if venta.servicio else 'Servicio no disponible',
                        'total': float(venta.total),
                        'metodo_pago': getattr(venta, 'metodo_pago', 'No especificado')
                    })
            else:
                # Si no existe el modelo, usar valores por defecto
                total_ventas = 0
                cantidad_ventas = 0
                ventas_detalle = []
                
        except Exception as e:
            # En caso de error, usar cálculo basado en citas como fallback
            print(f"Error calculando ventas: {e}")
            total_ventas = 0
            cantidad_ventas = 0
            ventas_detalle = []

        # También calcular citas completadas (para referencia)
        citas_completadas = Cita.objects.filter(
            manicurista=manicurista,
            fecha_cita__range=(fecha_inicio_obj, fecha_final_obj),
            estado='finalizada'
        )

        total_citas = citas_completadas.aggregate(
            total=Sum('precio_servicio')
        )['total'] or 0

        comision_citas = total_citas * 0.5

        # Si no hay ventas, usar el cálculo de citas como valor sugerido
        valor_sugerido = total_ventas if total_ventas > 0 else comision_citas

        return Response({
            'manicurista': {
                'id': manicurista.id,
                'nombre': f"{manicurista.nombres} {manicurista.apellidos}",
                'email': getattr(manicurista, 'email', '')
            },
            'periodo': {
                'fecha_inicio': fecha_inicio,
                'fecha_final': fecha_final
            },
            'resumen_ventas': {
                'total_ventas_completadas': float(total_ventas),
                'cantidad_ventas': cantidad_ventas,
                'promedio_por_venta': float(total_ventas / cantidad_ventas) if cantidad_ventas > 0 else 0
            },
            'resumen_citas': {
                'total_servicios_completados': float(total_citas),
                'citas_completadas_50_porciento': float(comision_citas),
                'cantidad_citas': citas_completadas.count()
            },
            'ventas_detalle': ventas_detalle,
            'valor_sugerido': float(valor_sugerido)  # Usar ventas o citas como fallback
        })

    @action(detail=False, methods=['post'])
    def calcular_citas_completadas(self, request):
        """
        Endpoint para calcular las citas completadas antes de crear la liquidación
        """
        manicurista_id = request.data.get('manicurista_id')
        fecha_inicio = request.data.get('fecha_inicio')
        fecha_final = request.data.get('fecha_final')

        if not all([manicurista_id, fecha_inicio, fecha_final]):
            return Response({
                "error": "Se requieren manicurista_id, fecha_inicio y fecha_final"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            manicurista = Manicurista.objects.get(id=manicurista_id)
        except Manicurista.DoesNotExist:
            return Response({"error": "Manicurista no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        # Calcular servicios completados
        citas_completadas = Cita.objects.filter(
            manicurista=manicurista,
            fecha_cita__range=(fecha_inicio, fecha_final),
            estado='finalizada'
        )

        total_servicios = citas_completadas.aggregate(
            total=Sum('precio_servicio')
        )['total'] or 0

        comision = total_servicios * 0.5
        cantidad_servicios = citas_completadas.count()

        # Obtener detalles de los servicios
        servicios_detalle = []
        for cita in citas_completadas:
            servicios_detalle.append({
                'fecha': cita.fecha_cita,
                'cliente': cita.cliente.nombre,
                'servicio': cita.servicio.nombre,
                'precio': float(cita.precio_servicio)
            })

        return Response({
            'manicurista': {
                'id': manicurista.id,
                'nombre': f"{manicurista.nombres} {manicurista.apellidos}"
            },
            'periodo': {
                'fecha_inicio': fecha_inicio,
                'fecha_final': fecha_final
            },
            'resumen': {
                'total_servicios_completados': float(total_servicios),
                'citas_completadas_50_porciento': float(comision),
                'cantidad_servicios': cantidad_servicios
            },
            'servicios_detalle': servicios_detalle
        })

    @action(detail=True, methods=['post'])
    def recalcular_citas_completadas(self, request, pk=None):
        """
        Recalcula las citas completadas para una liquidación específica
        """
        liquidacion = self.get_object()
        valor_anterior = liquidacion.citascompletadas
        nuevo_valor = liquidacion.recalcular_citas_completadas()
        
        return Response({
            'mensaje': 'Citas completadas recalculadas exitosamente',
            'valor_anterior': float(valor_anterior),
            'nuevo_valor': float(nuevo_valor),
            'diferencia': float(nuevo_valor - valor_anterior),
            'liquidacion': LiquidacionDetailSerializer(liquidacion).data
        })

    @action(detail=False, methods=['get'])
    def por_manicurista(self, request):
        manicurista_id = request.query_params.get('id')
        if manicurista_id:
            liquidaciones = Liquidacion.objects.filter(manicurista_id=manicurista_id)
            serializer = LiquidacionDetailSerializer(liquidaciones, many=True)
            return Response(serializer.data)
        return Response({"error": "Se requiere el ID del manicurista"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        liquidaciones = Liquidacion.objects.filter(estado='pendiente')
        serializer = LiquidacionDetailSerializer(liquidaciones, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def marcar_como_pagada(self, request, pk=None):
        liquidacion = self.get_object()
        if liquidacion.estado == 'pagado':
            return Response({"error": "Esta liquidación ya ha sido pagada"}, status=status.HTTP_400_BAD_REQUEST)
        liquidacion.estado = 'pagado'
        liquidacion.save()
        serializer = LiquidacionDetailSerializer(liquidacion)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def detalle_servicios(self, request, pk=None):
        """
        Obtiene el detalle de todos los servicios completados en el período de la liquidación
        """
        liquidacion = self.get_object()
        
        citas_completadas = Cita.objects.filter(
            manicurista=liquidacion.manicurista,
            fecha_cita__range=(liquidacion.fecha_inicio, liquidacion.fecha_final),
            estado='finalizada'
        ).select_related('cliente', 'servicio')

        servicios_detalle = []
        for cita in citas_completadas:
            servicios_detalle.append({
                'id': cita.id,
                'fecha': cita.fecha_cita,
                'hora': cita.hora_cita,
                'cliente': {
                    'id': cita.cliente.id,
                    'nombre': cita.cliente.nombre,
                    'documento': getattr(cita.cliente, 'documento', '')
                },
                'servicio': {
                    'id': cita.servicio.id,
                    'nombre': cita.servicio.nombre,
                    'precio': float(cita.precio_servicio)
                },
                'fecha_finalizacion': getattr(cita, 'fecha_finalizacion', None)
            })

        return Response({
            'liquidacion': {
                'id': liquidacion.id,
                'manicurista': f"{liquidacion.manicurista.nombres} {liquidacion.manicurista.apellidos}",
                'periodo': f"{liquidacion.fecha_inicio} - {liquidacion.fecha_final}",
                'total_servicios_completados': float(liquidacion.total_servicios_completados),
                'citascompletadas': float(liquidacion.citascompletadas),
                'cantidad_servicios': liquidacion.cantidad_servicios_completados,
                'total_a_pagar': float(liquidacion.total_a_pagar)
            },
            'servicios_detalle': servicios_detalle
        })
